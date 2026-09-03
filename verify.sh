#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PYTHON="${VLR_PYTHON:-$ROOT/.venv/bin/python}"
[[ -x "$PYTHON" ]] || PYTHON="$(command -v python3)"
"$PYTHON" -m py_compile app.py vlr_core.py vlr_runtime.py
bash -n setup setup.sh prepare-performance.sh storage-audit.sh vlr-podman.sh deploy_zinc.sh control.sh APPLY_TO_REPO.sh verify.sh


"$PYTHON" -m unittest discover -s tests -p 'test_*.py' -v
if command -v node >/dev/null 2>&1; then
  "$PYTHON" - <<'PY'
from pathlib import Path
s=Path('static/index_v3.html').read_text()
start=s.index('<script>')+len('<script>')
end=s.rindex('</script>')
Path('/tmp/vlr-extracted.js').write_text(s[start:end])
PY
  node --check /tmp/vlr-extracted.js
fi
printf '\nVLR 3.2 verification: PASS\n'
