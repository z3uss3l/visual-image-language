#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${HOME}/Infinity-Reconstruction-Lab"
REPORT="${ROOT}/logs/storage-audit-$(date +%Y%m%d-%H%M%S).txt"
mkdir -p "${ROOT}/logs"
exec > >(tee "$REPORT") 2>&1
printf 'VLR storage audit — %s\n\n' "$(date)"
printf 'Filesystem home:\n'; df -h "$HOME" || true
printf '\nVLR project:\n'; du -sh "$ROOT" 2>/dev/null || true
printf '\nPodman graphroot / storage:\n'
if command -v podman >/dev/null 2>&1; then
  podman info --format 'GraphRoot={{.Store.GraphRoot}}' 2>/dev/null || true
  GRAPHROOT="$(podman info --format '{{.Store.GraphRoot}}' 2>/dev/null || true)"
  [[ -n "$GRAPHROOT" && -d "$GRAPHROOT" ]] && df -h "$GRAPHROOT" || true
  podman system df 2>/dev/null || true
else
  echo 'podman: not installed'
fi
printf '\nLargest files under home (top 30):\n'; find "$HOME" -xdev -type f -printf '%s\t%p\n' 2>/dev/null | sort -nr | head -30 | awk '{printf "%.1f MB\t%s\n", $1/1048576, substr($0,index($0,$2))}' || true
printf '\nKnown caches:\n'
for d in "$HOME/.cache/pip" "$HOME/.cache/huggingface" "$HOME/.local/share/containers" "$HOME/.ollama" "$HOME/.local/share/Trash" "$HOME/.cache/uv" "$HOME/.npm"; do
  [[ -e "$d" ]] && du -sh "$d" 2>/dev/null || true
done
printf '\nNo files are deleted by this audit.\nReport: %s\n' "$REPORT"
