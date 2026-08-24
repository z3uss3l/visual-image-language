"""VLR runtime orchestration with explicit native/Podman capability checks."""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class RuntimeConfig:
    mode: str = field(default_factory=lambda: _runtime_mode())
    podman_bin: str = os.getenv("PODMAN_BIN", "podman")
    ollama_container: str = os.getenv("VLR_OLLAMA_CONTAINER", "vlr-ollama")
    comfy_container: str = os.getenv("VLR_COMFYUI_CONTAINER", "vlr-comfyui")
    ollama_image: str = os.getenv("VLR_OLLAMA_IMAGE", "docker.io/ollama/ollama:latest")
    comfy_image: str = os.getenv("VLR_COMFYUI_IMAGE", "")
    ollama_host_port: int = int(os.getenv("VLR_OLLAMA_PORT", "11435"))
    comfy_host_port: int = int(os.getenv("VLR_COMFYUI_PORT", "8189"))
    ollama_volume: str = os.getenv("VLR_OLLAMA_VOLUME", "vlr-ollama-models")
    comfy_volume: str = os.getenv("VLR_COMFYUI_VOLUME", "vlr-comfyui-data")
    start_timeout: int = int(os.getenv("VLR_RUNTIME_START_TIMEOUT", "180"))
    stop_timeout: int = int(os.getenv("VLR_RUNTIME_STOP_TIMEOUT", "30"))
    vulkan: bool = os.getenv("VLR_OLLAMA_VULKAN", "1") != "0"
    igpu_enable: bool = os.getenv("VLR_OLLAMA_IGPU_ENABLE", "1") != "0"
    max_vram: int = int(os.getenv("VLR_OLLAMA_MAX_VRAM", "0"))
    min_free_gib: float = float(os.getenv("VLR_PODMAN_MIN_FREE_GIB", "8"))
    min_model_free_gib: float = float(os.getenv("VLR_MODEL_MIN_FREE_GIB", "22"))


def _app_dir() -> Path:
    return Path(__file__).resolve().parent


def _runtime_mode() -> str:
    override = _app_dir() / "config" / "runtime.env"
    if override.is_file():
        for line in override.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("VLR_RUNTIME="):
                value = line.split("=", 1)[1].strip().lower()
                if value in {"native", "podman", "auto"}:
                    return value
    value = os.getenv("VLR_RUNTIME", "podman").lower()
    return value if value in {"native", "podman", "auto"} else "podman"


def set_runtime_mode(mode: str) -> str:
    mode = mode.lower().strip()
    if mode not in {"native", "podman", "auto"}:
        raise RuntimeErrorState(f"Unbekannte Runtime: {mode}")
    path = _app_dir() / "config" / "runtime.env"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# VLR GUI runtime selection\nVLR_RUNTIME={mode}\n", encoding="utf-8")
    return mode


def cfg() -> RuntimeConfig:
    return RuntimeConfig()


class RuntimeErrorState(RuntimeError):
    pass


def podman_exists() -> bool:
    return shutil.which(cfg().podman_bin) is not None


def _run(*args: str, check: bool = True, timeout: Optional[int] = None,
         stream: bool = False) -> subprocess.CompletedProcess:
    c = cfg()
    try:
        if stream:
            proc = subprocess.run([c.podman_bin, *args], check=check)
            return subprocess.CompletedProcess([c.podman_bin, *args], proc.returncode)
        return subprocess.run([c.podman_bin, *args], text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=check, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise RuntimeErrorState(str(exc)) from exc


def _ensure_image(image: str) -> None:
    if not image:
        raise RuntimeErrorState("Kein Container-Image konfiguriert.")
    inspect = _run("image", "exists", image, check=False, timeout=10)
    if inspect.returncode == 0:
        return
    storage = podman_storage_info()
    if storage.get("free_gib") is not None and storage["free_gib"] < cfg().min_free_gib:
        raise RuntimeErrorState(
            f"Zu wenig freier Speicher für den Podman-Image-Pull: {storage['free_gib']:.1f} GiB frei, "
            f"mindestens {cfg().min_free_gib:.1f} GiB erforderlich. Speicherpfad: {storage.get('graphroot','unbekannt')}"
        )
    print(f"[VLR] Container-Image fehlt lokal: {image}", flush=True)
    print("[VLR] Starte Podman-Pull. Der Image-Pull hat absichtlich keinen kurzen Timeout.", flush=True)
    try:
        _run("pull", image, stream=True)
    except KeyboardInterrupt as exc:
        raise RuntimeErrorState("Podman-Image-Pull abgebrochen; kein Container wurde gestartet.") from exc
    verify = _run("image", "exists", image, check=False, timeout=10)
    if verify.returncode != 0:
        raise RuntimeErrorState(f"Podman-Pull beendet, aber Image ist nicht lokal verfügbar: {image}")
    print(f"[VLR] Image bereit: {image}", flush=True)


def _container_exists(name: str) -> bool:
    return _run("container", "exists", name, check=False, timeout=5).returncode == 0


def _container_running(name: str) -> bool:
    if not _container_exists(name):
        return False
    r = _run("inspect", "--format", "{{.State.Running}}", name, check=False, timeout=5)
    return r.returncode == 0 and r.stdout.strip().lower() == "true"


def _ensure_volume(name: str) -> None:
    if _run("volume", "inspect", name, check=False, timeout=10).returncode != 0:
        _run("volume", "create", name, timeout=30)


def _gpu_args() -> list[str]:
    args: list[str] = []
    for dev in ("/dev/dri", "/dev/kfd"):
        if os.path.exists(dev):
            args += ["--device", dev]
    if os.path.exists("/dev/dri"):
        args += ["--group-add", "keep-groups"]
    return args


def _model_names(base_url: str) -> list[str]:
    import requests
    r = requests.get(f"{base_url}/api/tags", timeout=3)
    r.raise_for_status()
    return [str(x.get("name")) for x in r.json().get("models", []) if x.get("name")]


def _api_probe(base_url: str, model: str, vision: bool = False) -> dict:
    import requests
    result = {"url": base_url, "version": None, "models": [], "model_present": False,
              "chat": False, "vision": False, "error": None}
    try:
        v = requests.get(f"{base_url}/api/version", timeout=3)
        result["version"] = v.json().get("version") if v.ok else None
        result["models"] = _model_names(base_url)
        result["model_present"] = model in result["models"]
        if not result["model_present"]:
            result["error"] = f"Modell nicht vorhanden: {model}"
            return result
        r = requests.post(f"{base_url}/api/chat", json={"model": model,
            "messages":[{"role":"user","content":"Reply exactly OK."}],
            "stream":False,"options":{"temperature":0,"num_predict":2}}, timeout=30)
        if r.ok:
            result["chat"] = True
        else:
            result["error"] = f"/api/chat HTTP {r.status_code}: {r.text[:300]}"
        if vision and result["chat"]:
            # A 1x1 PNG is sufficient to verify that Ollama accepts image input.
            import base64, io
            from PIL import Image
            b = io.BytesIO(); Image.new("RGB", (1, 1), "black").save(b, "PNG")
            rr = requests.post(f"{base_url}/api/chat", json={"model": model,
                "messages":[{"role":"user","content":"Describe the image in one word.",
                              "images":[base64.b64encode(b.getvalue()).decode("ascii")]}],
                "stream":False,"options":{"temperature":0,"num_predict":8}}, timeout=60)
            result["vision"] = rr.ok
            if not rr.ok:
                result["error"] = f"Vision-Test HTTP {rr.status_code}: {rr.text[:300]}"
    except Exception as exc:
        result["error"] = str(exc)
    return result


def podman_storage_info() -> dict:
    result = {"graphroot": None, "free_bytes": None, "free_gib": None, "quota": None}
    if not podman_exists():
        return result
    try:
        r = _run("info", "--format", "{{.Store.GraphRoot}}", check=False, timeout=10)
        graphroot = r.stdout.strip() if r.returncode == 0 else ""
        if graphroot:
            result["graphroot"] = graphroot
            usage = shutil.disk_usage(graphroot)
            result["free_bytes"] = usage.free
            result["free_gib"] = usage.free / (1024 ** 3)
    except Exception:
        pass
    return result


def probe(mode: Optional[str] = None, model: Optional[str] = None) -> dict:
    c = cfg(); mode = mode or c.mode; model = model or os.getenv("OLLAMA_MODEL", "qwen3.8:27b")
    native_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    podman_url = f"http://127.0.0.1:{c.ollama_host_port}"
    out = {"selected": mode, "model": model,
           "native": {"mode":"native", "url":native_url},
           "podman": {"mode":"podman", "url":podman_url, "podman_available":podman_exists(),
                      "image":c.ollama_image, "image_present":False,
                      "container":c.ollama_container, "container_present":False,
                      "container_running":False, "storage":podman_storage_info()}}
    if mode in {"native", "auto"}:
        out["native"].update(_api_probe(native_url, model, vision=True))
    if mode in {"podman", "auto"} and podman_exists():
        out["podman"]["image_present"] = _run("image", "exists", c.ollama_image, check=False, timeout=10).returncode == 0
        out["podman"]["container_present"] = _container_exists(c.ollama_container)
        out["podman"]["container_running"] = _container_running(c.ollama_container)
        if out["podman"]["container_running"]:
            out["podman"].update(_api_probe(podman_url, model, vision=True))
        else:
            out["podman"]["error"] = "Ollama-Container ist nicht gestartet."
    return out


def start_ollama() -> dict:
    c = cfg()
    if not podman_exists():
        raise RuntimeErrorState("Podman ist nicht installiert/verfügbar.")
    _ensure_volume(c.ollama_volume)
    _ensure_image(c.ollama_image)
    if _container_running(c.ollama_container):
        return {"started": False, "running": True, "container": c.ollama_container}
    if _container_exists(c.ollama_container):
        _run("start", c.ollama_container, timeout=c.start_timeout)
    else:
        args = ["run", "-d", "--name", c.ollama_container,
                "-p", f"{c.ollama_host_port}:11434",
                "-v", f"{c.ollama_volume}:/root/.ollama", "--shm-size", "1g"]
        args += _gpu_args()
        if c.vulkan: args += ["-e", "OLLAMA_VULKAN=1"]
        if c.igpu_enable: args += ["-e", "OLLAMA_IGPU_ENABLE=1"]
        if c.max_vram > 0: args += ["-e", f"OLLAMA_MAX_VRAM={c.max_vram}"]
        args += [c.ollama_image]
        _run(*args, timeout=c.start_timeout)
    wait_http(f"http://127.0.0.1:{c.ollama_host_port}/api/tags", c.start_timeout, c.ollama_host_port)
    return {"started": True, "running": True, "container": c.ollama_container, "port": c.ollama_host_port}


def stop_ollama() -> dict:
    c = cfg()
    if not podman_exists() or not _container_exists(c.ollama_container):
        return {"stopped": False, "container": c.ollama_container}
    try:
        import requests
        requests.post(f"http://127.0.0.1:{c.ollama_host_port}/api/generate",
                      json={"model": os.getenv("OLLAMA_MODEL", ""), "prompt":"", "stream":False, "keep_alive":0}, timeout=15)
    except Exception:
        pass
    _run("stop", "-t", str(c.stop_timeout), c.ollama_container, check=False, timeout=c.stop_timeout + 10)
    return {"stopped": True, "container": c.ollama_container}


def start_comfyui() -> dict:
    c = cfg()
    if not podman_exists(): raise RuntimeErrorState("Podman ist nicht installiert/verfügbar.")
    if not c.comfy_image: raise RuntimeErrorState("VLR_COMFYUI_IMAGE ist im Podman-Modus nicht gesetzt.")
    _ensure_volume(c.comfy_volume); _ensure_image(c.comfy_image)
    if _container_running(c.comfy_container): return {"started":False,"running":True,"container":c.comfy_container}
    if _container_exists(c.comfy_container):
        _run("start", c.comfy_container, timeout=c.start_timeout)
    else:
        args=["run","-d","--name",c.comfy_container,"-p",f"{c.comfy_host_port}:8188","-v",f"{c.comfy_volume}:/workspace","--shm-size","2g"]
        args += _gpu_args(); args += [c.comfy_image]; _run(*args, timeout=c.start_timeout)
    wait_http(f"http://127.0.0.1:{c.comfy_host_port}/system_stats", c.start_timeout, c.comfy_host_port)
    return {"started":True,"running":True,"container":c.comfy_container,"port":c.comfy_host_port}


def stop_comfyui() -> dict:
    c=cfg()
    if not podman_exists() or not _container_exists(c.comfy_container): return {"stopped":False,"container":c.comfy_container}
    try:
        import requests
        requests.post(f"http://127.0.0.1:{c.comfy_host_port}/free",json={"unload_models":True,"free_memory":True},timeout=10)
    except Exception: pass
    _run("stop","-t",str(c.stop_timeout),c.comfy_container,check=False,timeout=c.stop_timeout+10)
    return {"stopped":True,"container":c.comfy_container}


def wait_http(url: str, timeout: int, expected_port: int, host_network: bool = False) -> None:
    import requests
    deadline=time.time()+timeout; last="not ready"
    while time.time()<deadline:
        try:
            r=requests.get(url,timeout=2)
            if r.ok:return
            last=f"HTTP {r.status_code}"
        except requests.RequestException as exc:last=str(exc)
        time.sleep(1)
    raise RuntimeErrorState(f"Runtime auf Port {expected_port} wurde nicht bereit: {last}")


def status() -> dict:
    c=cfg(); result={"mode":c.mode,"podman_available":podman_exists(),"ollama":{},"comfyui":{},"storage":podman_storage_info()}
    if podman_exists():
        result["ollama"]={"container":c.ollama_container,"exists":_container_exists(c.ollama_container),"running":_container_running(c.ollama_container),"port":c.ollama_host_port,"image":c.ollama_image}
        result["comfyui"]={"container":c.comfy_container,"exists":_container_exists(c.comfy_container),"running":_container_running(c.comfy_container),"port":c.comfy_host_port,"image":c.comfy_image or None}
    return result
