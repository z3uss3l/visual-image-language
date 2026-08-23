#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${HOME}/Infinity-Reconstruction-Lab"
MODEL="${MODEL:-qwen3-vl:4b}"
STATE_FILE="${APP_DIR}/.setup-state"
BACKUP_DIR="${APP_DIR}/.setup-backup"

log(){ printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
die(){ log "ERROR: $*"; exit 1; }

record_file(){
  local path="$1"
  mkdir -p "$APP_DIR"
  if [[ -f "$STATE_FILE" ]]; then
    grep -Fqx "$path" "$STATE_FILE" 2>/dev/null || printf '%s\n' "$path" >> "$STATE_FILE"
  else
    printf '%s\n' "$path" > "$STATE_FILE"
  fi
}

backup_if_needed(){
  local path="$1"
  if [[ -e "$path" && ! -e "${BACKUP_DIR}/$(basename "$path")" ]]; then
    mkdir -p "$BACKUP_DIR"
    cp -a "$path" "${BACKUP_DIR}/$(basename "$path")"
  fi
}

restore_backup_if_present(){
  local path="$1"
  local backup="${BACKUP_DIR}/$(basename "$path")"
  if [[ -f "$backup" ]]; then
    mkdir -p "$(dirname "$path")"
    cp -a "$backup" "$path"
  fi
}

rollback_project(){
  log "Rollback/Purge gestartet. Dabei werden nur project-spezifische Dateien entfernt und vorhandene Systempakete nicht verändert."

  if [[ -f "$STATE_FILE" ]]; then
    while IFS= read -r path; do
      [[ -z "$path" ]] && continue
      if [[ -e "$path" ]]; then
        rm -rf "$path"
      fi
    done < "$STATE_FILE"
  fi

  rm -rf "$APP_DIR/.venv" "$APP_DIR/.setup-state" "$APP_DIR/.setup-backup" "$APP_DIR/run.sh" "$APP_DIR/stop.sh" "$APP_DIR/config" "$APP_DIR/logs" "$APP_DIR/archive" "$APP_DIR/static" "$APP_DIR/app.py" "$APP_DIR/README.md"

  if [[ -d "$APP_DIR" ]]; then
    rmdir "$APP_DIR" 2>/dev/null || true
  fi

  log "Rollback abgeschlossen. Bereits vorhandene Systempakete wurden nicht entfernt."
}

usage(){
  cat <<'EOF'
Usage:
  ./setup.sh              Install the project in $HOME/Infinity-Reconstruction-Lab
  ./setup.sh --rollback   Remove only project-managed files and restore previous state if backups exist
  ./setup.sh --purge      Alias for rollback
  ./setup.sh --help       Show this help

Notes:
  - This script never removes previously installed system packages.
  - It only manages project-local files and the local Python venv.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ "${1:-}" == "--rollback" || "${1:-}" == "--purge" ]]; then
  rollback_project
  exit 0
fi

if [[ "${1:-}" != "" && "${1:-}" != "install" ]]; then
  die "Unbekannte Option: $1"
fi

log "Infinity Reconstruction Lab — VLR Prototype v2"
command -v python3 >/dev/null || die "python3 fehlt."
command -v curl >/dev/null || die "curl fehlt."

mkdir -p "$APP_DIR"/{static,archive,logs,config}
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# preserve previously existing project files if present, but never touch system packages
backup_if_needed "$APP_DIR/app.py"
backup_if_needed "$APP_DIR/README.md"
backup_if_needed "$APP_DIR/static/index.html"

cp -f "$SCRIPT_DIR"/app.py "$APP_DIR"/app.py
cp -f "$SCRIPT_DIR"/README.md "$APP_DIR"/README.md
cp -f "$SCRIPT_DIR"/static/index.html "$APP_DIR"/static/index.html

record_file "$APP_DIR/app.py"
record_file "$APP_DIR/README.md"
record_file "$APP_DIR/static/index.html"
record_file "$APP_DIR/run.sh"
record_file "$APP_DIR/stop.sh"
record_file "$APP_DIR/config/defaults.env"
record_file "$APP_DIR/.venv"

python3 -m venv "$APP_DIR/.venv"
source "$APP_DIR/.venv/bin/activate"
python -m pip install --upgrade pip
python -m pip install --upgrade fastapi uvicorn python-multipart pillow numpy opencv-python-headless scikit-image requests

if command -v ollama >/dev/null 2>&1; then
  log "Ollama vorhanden: $(ollama --version || true)"
  if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    log "Ollama ist installiert, aber nicht erreichbar. Kein automatischer Systemdienst-Eingriff."
    log "Falls gewünscht: 'ollama serve' in einem separaten Terminal starten."
  fi
  if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    log "Vision-Modell prüfen: $MODEL"
    ollama pull "$MODEL" || log "WARNUNG: Modell konnte nicht automatisch geladen werden."
  fi
else
  log "Ollama nicht installiert. Für die kostenlose Offline-Lösung Ollama installieren und erneut starten."
fi

cat > "$APP_DIR/run.sh" <<'RUN'
#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$APP_DIR/.venv/bin/activate"
cd "$APP_DIR"
exec python app.py
RUN
chmod +x "$APP_DIR/run.sh"

cat > "$APP_DIR/stop.sh" <<'STOP'
#!/usr/bin/env bash
pkill -f "python .*Infinity-Reconstruction-Lab/app.py" 2>/dev/null || true
STOP
chmod +x "$APP_DIR/stop.sh"

cat > "$APP_DIR/config/defaults.env" <<'CFG'
OLLAMA_MODEL=qwen3-vl:4b
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_TIMEOUT=300
COMFYUI_URL=http://127.0.0.1:8188
COMFYUI_WORKFLOW=$APP_DIR/config/comfyui-workflow.json
HOST=127.0.0.1
PORT=8765
CFG

log "Setup abgeschlossen."
log "Start: $APP_DIR/run.sh"
log "Browser: http://127.0.0.1:8765"
log "Purge/Rollback: ./setup.sh --purge"

