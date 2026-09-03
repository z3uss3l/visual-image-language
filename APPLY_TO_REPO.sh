#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-.}"
cd "$TARGET"

for f in APPLY_TO_REPO.sh app.py vlr_core.py vlr_runtime.py README.md setup setup.sh prepare-performance.sh storage-audit.sh vlr-podman.sh deploy_zinc.sh control.sh CONTAINER_RUNTIME.md verify.sh COMMIT_MESSAGE.txt requirements.txt; do
  mkdir -p "$(dirname "$f")"
  cp -f "$ROOT/$f" "$f"
done


mkdir -p static tests config config/quadlet
cp -f "$ROOT/static/index_v3.html" static/index_v3.html
cp -f "$ROOT/tests/"test_*.py tests/
cp -f "$ROOT/config/defaults.env" config/defaults.env
cp -f "$ROOT/config/quadlet/"* config/quadlet/

# The repository previously carried intermediate prototype ZIPs. They are release
# artifacts, not source, and are intentionally removed from the working tree.
for f in infinity-reconstruction-lab-vlr-v2.zip infinity-reconstruction-lab-vlr-v3.zip; do
  if [[ -f "$f" ]]; then
    if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then git rm -f "$f"; else rm -f "$f"; fi
  fi
done

./verify.sh

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git diff --check
fi
printf '\nReady for commit.\n'
printf 'Suggested commit: %s' "$(cat COMMIT_MESSAGE.txt)"
printf '\nThen: git add -A && git commit -F COMMIT_MESSAGE.txt && git push origin dev\n'

