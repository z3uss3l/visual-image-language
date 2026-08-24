#!/usr/bin/env bash
set -Eeuo pipefail
DRY=0
[[ "${1:-}" == "--dry-run" ]] && DRY=1
log(){ printf '[VLR-PERF] %s\n' "$*"; }
# Only user-facing desktop applications. Never stop system daemons, security, network, display, audio or update services.
SAFE_APPS=(steam discord slack teams spotify obs firefox chrome chromium code code-oss)
for app in "${SAFE_APPS[@]}"; do
  if pgrep -u "$USER" -x "$app" >/dev/null 2>&1; then
    if [[ "$DRY" == 1 ]]; then log "würde schließen: $app"; else pkill -TERM -u "$USER" -x "$app" 2>/dev/null || true; log "geschlossen/angefordert: $app"; fi
  fi
done

# VLR Podman mode must not compete with a separately managed native Ollama.
# Only stop the explicitly named Ollama service if it exists; never touch arbitrary services.
if [[ "${VLR_RUNTIME:-podman}" == "podman" ]]; then
  for scope in --user ""; do
    if systemctl $scope list-unit-files ollama.service >/dev/null 2>&1 && systemctl $scope is-active --quiet ollama.service; then
      if [[ "$DRY" == 1 ]]; then
        log "würde Ollama-Service stoppen: ${scope:-system}"
      else
        systemctl $scope stop ollama.service 2>/dev/null || log "Ollama-Service konnte nicht gestoppt werden; bitte vor VLR-Start prüfen."
      fi
    fi
  done
fi

if command -v sync >/dev/null; then sync; fi
if command -v powerprofilesctl >/dev/null 2>&1; then
  if [[ "$DRY" == 1 ]]; then log "power profile aktuell: $(powerprofilesctl get 2>/dev/null || true)"; else powerprofilesctl set performance 2>/dev/null || log "Performance-Profil nicht verfügbar; unverändert."; fi
fi
if command -v systemctl >/dev/null 2>&1; then systemctl --user reset-failed 2>/dev/null || true; fi
log "Keine Systemdienste wurden deaktiviert."
