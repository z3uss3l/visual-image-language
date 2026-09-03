#!/usr/bin/env bash
# control.sh - Usability-Optimized HCI Control Script for VLR 3.2
set -Eeuo pipefail

APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

# Colors & Formatting
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

log_info(){ printf "${BLUE}[INFO]${NC} %s\n" "$*"; }
log_ok(){ printf "${GREEN}[OK]${NC} %s\n" "$*"; }
log_warn(){ printf "${YELLOW}[WARN]${NC} %s\n" "$*"; }
log_err(){ printf "${RED}[ERROR]${NC} %s\n" "$*"; }

banner(){
  clear 2>/dev/null || true
  printf "${CYAN}${BOLD}"
  printf "===========================================================\n"
  printf "       VLR 3.2 — HCI CONTAINER & CONTROL DASHBOARD          \n"
  printf "===========================================================\n"
  printf "${NC}\n"
}

get_status_summary(){
  if command -v podman >/dev/null 2>&1; then
    OLLAMA_RUNNING=$(podman inspect -f '{{.State.Running}}' vlr-ollama 2>/dev/null || echo "false")
    COMFY_RUNNING=$(podman inspect -f '{{.State.Running}}' vlr-comfyui 2>/dev/null || echo "false")
  else
    OLLAMA_RUNNING="false"
    COMFY_RUNNING="false"
  fi
}

show_status(){
  get_status_summary
  printf "${BOLD}System & Container Status:${NC}\n"
  if [[ "$OLLAMA_RUNNING" == "true" ]]; then
    printf "  • Ollama Container (vlr-ollama):  ${GREEN}● RUNNING${NC} (Port 11435)\n"
  else
    printf "  • Ollama Container (vlr-ollama):  ${RED}○ STOPPED / PURGED${NC}\n"
  fi

  if [[ "$COMFY_RUNNING" == "true" ]]; then
    printf "  • ComfyUI Container (vlr-comfyui): ${GREEN}● RUNNING${NC} (Port 8189)\n"
  else
    printf "  • ComfyUI Container (vlr-comfyui): ${RED}○ STOPPED / PURGED${NC}\n"
  fi

  if pgrep -f "python .*app.py" >/dev/null 2>&1; then
    printf "  • VLR Web App (app.py):           ${GREEN}● ACTIVE${NC} (http://127.0.0.1:8765)\n"
  else
    printf "  • VLR Web App (app.py):           ${YELLOW}○ INACTIVE${NC}\n"
  fi
  printf "\n"
}

cmd_start(){
  banner
  log_info "Deploying & Starting VLR Containers..."
  if [[ -x "$APP_DIR/prepare-performance.sh" ]]; then
    "$APP_DIR/prepare-performance.sh" --apply || true
  fi

  if [[ -x "$APP_DIR/vlr-podman.sh" ]]; then
    log_info "Starting Ollama container on port 11435..."
    "$APP_DIR/vlr-podman.sh" start-ollama || log_warn "Ollama container start failed or already running."
  else
    log_err "vlr-podman.sh script missing."
    return 1
  fi
  log_ok "Container deployment & startup sequence complete."
}

cmd_stop(){
  banner
  log_info "Stopping and Purging VLR Containers..."
  if [[ -x "$APP_DIR/vlr-podman.sh" ]]; then
    "$APP_DIR/vlr-podman.sh" stop-all || true
  fi

  if command -v podman >/dev/null 2>&1; then
    log_info "Purging container instances (vlr-ollama, vlr-comfyui)..."
    podman rm -f vlr-ollama vlr-comfyui 2>/dev/null || true
  fi

  log_info "Stopping any active host web application processes..."
  pkill -f "python .*app.py" 2>/dev/null || true
  if command -v sync >/dev/null 2>&1; then sync; fi
  log_ok "Containers purged and processes stopped successfully."
}

cmd_doctor(){
  banner
  log_info "Running System Diagnostics & Preflight Checks..."
  if [[ -x "$APP_DIR/vlr-podman.sh" ]]; then
    "$APP_DIR/vlr-podman.sh" doctor
  else
    log_err "vlr-podman.sh missing."
  fi
}

cmd_audit(){
  banner
  if [[ -x "$APP_DIR/storage-audit.sh" ]]; then
    "$APP_DIR/storage-audit.sh"
  else
    log_err "storage-audit.sh missing."
  fi
}

cmd_verify(){
  banner
  log_info "Running VLR 3.2 Unit Test & Verification Suite..."
  if [[ -x "$APP_DIR/verify.sh" ]]; then
    "$APP_DIR/verify.sh"
  else
    log_err "verify.sh missing."
  fi
}

menu(){
  while true; do
    banner
    show_status
    printf "${BOLD}Select an action:${NC}\n"
    printf "  ${GREEN}[1] Start${NC}   - Deploy in & Start Containers (Ollama / ComfyUI)\n"
    printf "  ${RED}[2] Stop${NC}    - Purge Containers & Stop App Processes\n"
    printf "  ${CYAN}[3] Status${NC}  - Show Detailed Runtime & Storage Status\n"
    printf "  ${YELLOW}[4] Doctor${NC}  - Run Preflight Hardware & Storage Doctor\n"
    printf "  ${BLUE}[5] Audit${NC}   - Run Storage Audit Report\n"
    printf "  ${CYAN}[6] Verify${NC}  - Run Automated Test Suite (verify.sh)\n"
    printf "  ${BOLD}[Q] Quit${NC}    - Exit Menu\n\n"
    printf "${BOLD}Choice [1-6, Q]: ${NC}"

    read -r choice || break
    case "$choice" in
      1|[sS]|[sS][tT][aA][rR][tT]|[dD][eE][pP][lL][oO][yY])
        cmd_start
        printf "\nPress Enter to return to menu..."; read -r _ || true
        ;;
      2|[kK]|[sS][tT][oO][pP]|[pP][uU][rR][gG][eE])
        cmd_stop
        printf "\nPress Enter to return to menu..."; read -r _ || true
        ;;
      3|[sS][tT][aA][tT][uU][sS])
        banner
        show_status
        if [[ -x "$APP_DIR/vlr-podman.sh" ]]; then
          "$APP_DIR/vlr-podman.sh" status
        fi
        printf "\nPress Enter to return to menu..."; read -r _ || true
        ;;
      4|[dD][oO][cC][tT][oO][rR])
        cmd_doctor
        printf "\nPress Enter to return to menu..."; read -r _ || true
        ;;
      5|[aA][uU][dD][iI][tT])
        cmd_audit
        printf "\nPress Enter to return to menu..."; read -r _ || true
        ;;
      6|[vV][eE][rR][iI][fF][yY])
        cmd_verify
        printf "\nPress Enter to return to menu..."; read -r _ || true
        ;;
      [qQ]|[eE][xX][iI][tT])
        log_info "Exiting control menu."
        exit 0
        ;;
      *)
        log_warn "Invalid option: $choice"
        sleep 1
        ;;
    esac
  done
}

usage(){
  cat <<EOF
VLR 3.2 Usability Control CLI & Menu Script

Usage:
  ./control.sh                  Launch interactive HCI Control Menu
  ./control.sh start            Deploy in and start containers (Start)
  ./control.sh stop             Stop and purge containers (Stop / Purge)
  ./control.sh status           Show runtime and container status
  ./control.sh doctor           Run diagnostic preflight doctor
  ./control.sh audit            Run storage audit
  ./control.sh verify           Run test suite
  ./control.sh --help           Show this help message
EOF
}

case "${1:-}" in
  ""|menu|--menu) menu ;;
  start|Start|deploy) cmd_start ;;
  stop|Stop|purge|Purge) cmd_stop ;;
  status|Status)
    show_status
    if [[ -x "$APP_DIR/vlr-podman.sh" ]]; then "$APP_DIR/vlr-podman.sh" status; fi
    ;;
  doctor|Doctor) cmd_doctor ;;
  audit|Audit) cmd_audit ;;
  verify|Verify) cmd_verify ;;
  help|-h|--help) usage ;;
  *) log_err "Unknown command: $1"; usage; exit 2 ;;
esac
