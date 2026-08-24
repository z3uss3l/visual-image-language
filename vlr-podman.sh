#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${APP_DIR}/config/defaults.env"
[[ -f "$ENV_FILE" ]] && source "$ENV_FILE"
[[ -f "${APP_DIR}/config/runtime.env" ]] && source "${APP_DIR}/config/runtime.env"
export VLR_RUNTIME=podman
PYTHON="${APP_DIR}/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="$(command -v python3)"
export PODMAN_BIN="${PODMAN_BIN:-podman}"
export VLR_OLLAMA_IMAGE="${VLR_OLLAMA_IMAGE:-docker.io/ollama/ollama:latest}"
export VLR_OLLAMA_CONTAINER="${VLR_OLLAMA_CONTAINER:-vlr-ollama}"
export VLR_OLLAMA_VOLUME="${VLR_OLLAMA_VOLUME:-vlr-ollama-models}"
export VLR_OLLAMA_PORT="${VLR_OLLAMA_PORT:-11435}"
export VLR_COMFYUI_CONTAINER="${VLR_COMFYUI_CONTAINER:-vlr-comfyui}"
export VLR_COMFYUI_VOLUME="${VLR_COMFYUI_VOLUME:-vlr-comfyui-data}"
export VLR_COMFYUI_PORT="${VLR_COMFYUI_PORT:-8189}"
export VLR_COMFYUI_IMAGE="${VLR_COMFYUI_IMAGE:-ghcr.io/ai-dock/comfyui:latest}"

usage(){ echo "Usage: $0 {status|doctor|preflight|start-ollama|stop-ollama|start-comfyui|stop-comfyui|stop-all|pull-model [MODEL]}"; }
need(){ command -v "$PODMAN_BIN" >/dev/null || { echo "Podman fehlt." >&2; exit 2; }; }
runpy(){ "$PYTHON" - "$@"; }
status(){ runpy <<'PY'
from vlr_runtime import status
import json
print(json.dumps(status(), indent=2))
PY
}
doctor(){ need; runpy <<'PY'
from vlr_runtime import probe, podman_storage_info
import json, os
print('Podman:', os.popen('podman --version').read().strip())
print('Rootless:', os.popen("podman info --format '{{.Host.Security.Rootless}}' 2>/dev/null").read().strip())
print('GPU devices:')
for p in ('/dev/dri/card1','/dev/dri/renderD128','/dev/kfd'):
    print(' ', p, 'OK' if os.path.exists(p) else 'missing')
print('Storage:')
print(json.dumps(podman_storage_info(), indent=2))
print('Runtime/model probe:')
print(json.dumps(probe(model=os.getenv('OLLAMA_MODEL','qwen3.8:27b')), indent=2))
PY
}
preflight(){ need; runpy <<'PY'
from vlr_runtime import podman_storage_info, cfg
import json
s=podman_storage_info(); c=cfg()
print(json.dumps({'storage':s,'min_free_for_image_gib':c.min_free_gib,'min_free_for_model_gib':c.min_model_free_gib,'ollama_image':c.ollama_image,'model':__import__('os').getenv('OLLAMA_MODEL','qwen3.8:27b')}, indent=2))
PY
}
start_ollama(){ need; runpy <<'PY'
from vlr_runtime import start_ollama
print(start_ollama())
PY
}
stop_ollama(){ need; runpy <<'PY'
from vlr_runtime import stop_ollama
print(stop_ollama())
PY
}
start_comfyui(){ need; runpy <<'PY'
from vlr_runtime import start_comfyui
print(start_comfyui())
PY
}
stop_comfyui(){ need; runpy <<'PY'
from vlr_runtime import stop_comfyui
print(stop_comfyui())
PY
}
stop_all(){ stop_comfyui || true; stop_ollama || true; }
pull_model(){
  need
  MODEL="${1:-${OLLAMA_MODEL:-qwen3.8:27b}}"
  start_ollama
  cleanup(){ "$PYTHON" - <<'PY'
from vlr_runtime import stop_ollama
try: print(stop_ollama())
except Exception as exc: print(exc)
PY
  }
  trap cleanup EXIT INT TERM
  "$PODMAN_BIN" exec "$VLR_OLLAMA_CONTAINER" ollama pull "$MODEL"
  "$PODMAN_BIN" exec "$VLR_OLLAMA_CONTAINER" ollama show "$MODEL" >/dev/null
  echo "[VLR] Modell bereit im persistenten Volume: $MODEL"
}
need
case "${1:-}" in
 status) status;; doctor) doctor;; preflight) preflight;; start-ollama) start_ollama;; stop-ollama) stop_ollama;; start-comfyui) start_comfyui;; stop-comfyui) stop_comfyui;; stop-all) stop_all;; pull-model) pull_model "${2:-}";; *) usage; exit 2;; esac
