# Podman runtime

VLR supports a **Podman-first runtime**. It never requires two large AI models to remain resident at the same time.

## Phase contract

1. Ollama/ Qwen phase starts the managed `vlr-ollama` container.
2. Vision/reasoning requests finish.
3. Qwen is asked to unload (`keep_alive: 0`).
4. The Ollama container is stopped.
5. ComfyUI starts only after the Ollama phase is gone.
6. Image generation completes.
7. ComfyUI receives `/free` and its container is stopped.
8. Evaluation runs on the host.

This gives both model-level and process-level memory boundaries.

## Bazzite / AMD

Podman is used rootless. The runtime passes `/dev/dri` and `/dev/kfd` only when present and uses `--group-add keep-groups`. This follows Podman's documented rootless device behavior. SELinux device policy is **not** changed automatically; if the host blocks device access, configure it explicitly after inspecting the error.

Ollama's official container supports AMD ROCm and Vulkan; the runtime enables Vulkan by default. The Radeon 780M is the target iGPU; Vulkan is the preferred first path for Ollama, with `/dev/kfd` passed only when present.

## Configuration

`config/defaults.env` contains:

- `VLR_RUNTIME=podman` — default and recommended on the target Bazzite host; require the managed Podman phases.
- `VLR_RUNTIME=auto` — optional compatibility mode with native fallback.
- `VLR_RUNTIME=native` — disable container orchestration.
- `VLR_COMFYUI_IMAGE` — required for Podman ComfyUI phase.
- `VLR_OLLAMA_IMAGE` — defaults to the official Ollama image.

The default Podman ports are **11435** and **8189** so an existing native Ollama/ComfyUI installation on 11434/8188 is not accidentally displaced.

## Commands

```bash
./vlr-podman.sh doctor
./vlr-podman.sh status
./vlr-podman.sh start-ollama
./vlr-podman.sh stop-ollama
./vlr-podman.sh pull-model qwen3.8:27b
./vlr-podman.sh start-comfyui
./vlr-podman.sh stop-comfyui
./vlr-podman.sh stop-all
```

The model volume is persistent. Stopping/removing the container does **not** delete the model.
