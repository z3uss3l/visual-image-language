#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR="${VLR_APP_DIR:-${HOME}/Infinity-Reconstruction-Lab}"
MODEL="${MODEL:-qwen3.8:27b}"
STATE_FILE="${APP_DIR}/.setup-state"
BACKUP_DIR="${APP_DIR}/.setup-backup"

log(){ printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
die(){ log "ERROR: $*"; exit 1; }
trap 'rc=$?; log "SETUP FEHLER: Zeile ${LINENO}, Befehl: ${BASH_COMMAND}, Exit: ${rc}"; exit "$rc"' ERR

usage(){ cat <<'EOF'
Usage:
  ./setup.sh              Install/update the project in ~/Infinity-Reconstruction-Lab
  ./setup.sh --rollback   Remove only project-managed files
  ./setup.sh --help       Show this help

Default model: qwen3.8:27b
Override: MODEL='other-model' ./setup.sh

The setup does not install system services or remove system packages.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then usage; exit 0; fi

rollback(){
  log "Project-Rollback: nur projektverwaltete Dateien werden entfernt."
  if [[ -f "$STATE_FILE" ]]; then while IFS= read -r p; do [[ -e "$p" ]] && rm -rf "$p"; done < "$STATE_FILE"; fi
  rm -rf "$APP_DIR/.venv" "$APP_DIR/.setup-state" "$APP_DIR/.setup-backup" "$APP_DIR/run.sh" "$APP_DIR/prepare-performance.sh" "$APP_DIR/storage-audit.sh" "$APP_DIR/stop.sh" "$APP_DIR/vlr-podman.sh" "$APP_DIR/config" "$APP_DIR/static" "$APP_DIR/app.py" "$APP_DIR/vlr_core.py" "$APP_DIR/vlr_runtime.py" "$APP_DIR/README.md" "$APP_DIR/setup" "$APP_DIR/setup.sh"
  rmdir "$APP_DIR" 2>/dev/null || true
}
if [[ "${1:-}" == "--rollback" || "${1:-}" == "--purge" ]]; then rollback; exit 0; fi
[[ "${1:-}" == "" || "${1:-}" == "install" ]] || die "Unbekannte Option: $1"

command -v python3 >/dev/null || die "python3 fehlt."
command -v curl >/dev/null || die "curl fehlt."
mkdir -p "$APP_DIR"/{static,archive,logs,config,tests,config/quadlet}
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

FILES=(
  app.py vlr_core.py vlr_runtime.py README.md CONTAINER_RUNTIME.md COMMIT_MESSAGE.txt verify.sh setup setup.sh
  requirements.txt
  static/index_v3.html
  tests/test_runtime.py tests/test_api.py tests/test_runtime_commands.py
  config/quadlet/README.md config/quadlet/vlr-ollama.container config/quadlet/vlr-comfyui.container
)
for f in "${FILES[@]}"; do
  [[ -f "$SCRIPT_DIR/$f" ]] || die "Paket unvollständig: Quelle fehlt: $SCRIPT_DIR/$f"
  dest="$APP_DIR/$f"
  mkdir -p "$(dirname "$dest")"
  if [[ -f "$dest" ]]; then
    backup="$BACKUP_DIR/$f"
    mkdir -p "$(dirname "$backup")"
    cp -a "$dest" "$backup"
  fi
  cp -f "$SCRIPT_DIR/$f" "$dest"
  grep -Fqx "$dest" "$STATE_FILE" 2>/dev/null || echo "$dest" >> "$STATE_FILE"
done

cat > "$APP_DIR/config/defaults.env" <<CFG
OLLAMA_MODEL=$MODEL
OLLAMA_URL=http://127.0.0.1:11435
OLLAMA_TIMEOUT=600
VLR_RUNTIME_START_TIMEOUT=180
VLR_IMAGE_PULL_TIMEOUT=0
OLLAMA_PHASE_KEEP_ALIVE=5m
VLR_RUNTIME=podman
PODMAN_BIN=podman
VLR_OLLAMA_IMAGE=docker.io/ollama/ollama:latest
VLR_OLLAMA_CONTAINER=vlr-ollama
VLR_OLLAMA_VOLUME=vlr-ollama-models
VLR_OLLAMA_PORT=11435
VLR_OLLAMA_VULKAN=1
VLR_OLLAMA_IGPU_ENABLE=1
VLR_OLLAMA_MAX_VRAM=0
VLR_COMFYUI_IMAGE=ghcr.io/ai-dock/comfyui:latest
VLR_COMFYUI_CONTAINER=vlr-comfyui
VLR_COMFYUI_VOLUME=vlr-comfyui-data
VLR_COMFYUI_PORT=8189
COMFYUI_URL=http://127.0.0.1:8189
COMFYUI_WORKFLOW=$APP_DIR/config/comfyui-workflow.json
HOST=127.0.0.1
PORT=8765
RETENTION_LAST=5
RETENTION_KEEP_IMPROVEMENTS=1
RETENTION_MIN_IMPROVEMENT=0.005
CFG
printf '%s\n' "$APP_DIR/config/defaults.env" >> "$STATE_FILE"

if [[ ! -x "$APP_DIR/.venv/bin/python" ]]; then
  python3 -m venv "$APP_DIR/.venv"
fi
source "$APP_DIR/.venv/bin/activate"
python -m pip install --disable-pip-version-check --no-cache-dir --timeout "${PIP_TIMEOUT:-15}" --retries "${PIP_RETRIES:-2}" fastapi uvicorn python-multipart httpx pillow numpy opencv-python-headless scikit-image requests psutil
python - <<'PY'
mods = ("fastapi", "uvicorn", "multipart", "httpx", "PIL", "numpy", "cv2", "skimage", "requests", "psutil")
missing=[]
for name in mods:
    try:
        __import__(name)
    except Exception as exc:
        missing.append(f"{name}: {exc}")
if missing:
    raise SystemExit("Python-Abhängigkeiten fehlen nach Installation:\n" + "\n".join(missing))
print("Python-Abhängigkeiten: PASS")
PY
cp -f "$SCRIPT_DIR/prepare-performance.sh" "$APP_DIR/prepare-performance.sh"
chmod +x "$APP_DIR/prepare-performance.sh"
printf '%s\n' "$APP_DIR/prepare-performance.sh" >> "$STATE_FILE"

cp -f "$SCRIPT_DIR/storage-audit.sh" "$APP_DIR/storage-audit.sh"
chmod +x "$APP_DIR/storage-audit.sh"
cp -f "$SCRIPT_DIR/vlr-podman.sh" "$APP_DIR/vlr-podman.sh"
chmod +x "$APP_DIR/vlr-podman.sh"
printf '%s\n' "$APP_DIR/vlr-podman.sh" >> "$STATE_FILE"
printf '%s\n' "$APP_DIR/storage-audit.sh" >> "$STATE_FILE"

cat > "$APP_DIR/run.sh" <<'RUN'
#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$APP_DIR/config/defaults.env"
source "$APP_DIR/.venv/bin/activate"
"$APP_DIR/prepare-performance.sh" --apply
cd "$APP_DIR"
exec python app.py
RUN
chmod +x "$APP_DIR/run.sh"
printf '%s\n' "$APP_DIR/run.sh" >> "$STATE_FILE"

cat > "$APP_DIR/stop.sh" <<'STOP'
#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
pkill -f "python .*Infinity-Reconstruction-Lab/app.py" 2>/dev/null || true
if [[ -x "$APP_DIR/vlr-podman.sh" ]]; then
  "$APP_DIR/vlr-podman.sh" stop-all || true
fi
STOP
chmod +x "$APP_DIR/stop.sh"
printf '%s\n' "$APP_DIR/stop.sh" >> "$STATE_FILE"

if command -v ollama >/dev/null 2>&1; then
  log "Ollama gefunden: $(ollama --version 2>/dev/null || true)"
  # VLR 3.2 defaults to the isolated Podman endpoint. Never probe the native
  # 11434 endpoint and then claim the configured model is missing. The model
  # is checked by the runtime doctor after the container is started.
  log "Modellprüfung erfolgt über den konfigurierten VLR-Runtime-Endpunkt (Podman: 11435)."
else
  log "Ollama CLI nicht installiert; das ist bei Podman-Betrieb zulässig."
fi

# Setup is installation-only. Never start Ollama, ComfyUI or the web app here.
for required in "$APP_DIR/run.sh" "$APP_DIR/vlr-podman.sh" "$APP_DIR/verify.sh" "$APP_DIR/config/defaults.env"; do
  [[ -f "$required" ]] || die "Installation unvollständig: fehlt: $required"
done

"$APP_DIR/verify.sh"
log "Host-Python ist absichtlich torch-frei; ComfyUI/Torch laufen ausschließlich in der Bildgenerator-Runtime."
log "VLR 3.2 Setup abgeschlossen."
log "Setup startet keine KI-Runtime automatisch."
log "Setup-Script: $APP_DIR/setup"
log "Start: $APP_DIR/run.sh"
log "Browser: http://127.0.0.1:8765"
log "Retention default: letzte 5 Generationen + Verbesserungen + Gewinner/Best geschützt"
