#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${HOME}/Infinity-Reconstruction-Lab"
MODEL="${MODEL:-qwen3-vl:4b}"

log(){ printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
die(){ log "ERROR: $*"; exit 1; }
trap 'die "Fehler in Zeile $LINENO: $BASH_COMMAND"' ERR

log "Infinity Reconstruction Lab — VLR Prototype v2"

command -v python3 >/dev/null || die "python3 fehlt."
command -v curl >/dev/null || die "curl fehlt."

mkdir -p "$APP_DIR"/{static,archive,logs,config}
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cp -f "$SCRIPT_DIR"/app.py "$APP_DIR"/app.py
cp -f "$SCRIPT_DIR"/README.md "$APP_DIR"/README.md
cp -f "$SCRIPT_DIR"/static/index.html "$APP_DIR"/static/index.html

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
  log "Ollama nicht installiert. Lokaler Visionpfad bleibt deaktiviert."
  log "Der Prototyp kann zunächst mit Puter laufen; für vollständig lokale Experimente Ollama separat installieren."
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
HOST=127.0.0.1
PORT=8765
CFG

log "Setup abgeschlossen."
log "Start: $APP_DIR/run.sh"
log "Browser: http://127.0.0.1:8765"
