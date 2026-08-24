# VLR 3.2 verification report

Target: Bazzite + Radeon 780M + 32 GB shared RAM.

Checks completed in the release workspace:

- Python syntax: PASS
- Bash syntax: PASS
- JavaScript syntax: PASS
- FastAPI smoke tests: PASS
- image comparison: PASS
- Podman runtime command tests: PASS
- runtime endpoint separation (11435/8189): PASS
- setup source-tree/idempotency checks: PASS
- total automated tests: 10/10 PASS
- `git diff --check` on an apply-test checkout: PASS

Not performed in this build environment:

- real Radeon 780M GPU inference
- real Podman GPU device access on Bazzite
- real Qwen3.8:27B inference
- real ComfyUI generation

Those require the target host and are deliberately verified by the local doctor/first-run sequence.

- Setup repair: self-contained target setup wrapper, explicit ERR diagnostics, and installation-only behavior: PASS
- Podman image pull: no short subprocess timeout; image existence verified before container creation: PASS
