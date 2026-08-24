# Quadlet templates

These are templates for Bazzite/Fedora rootless Podman. VLR intentionally uses `Restart=no`: the controller starts exactly one AI phase and stops it after the phase.

Copy to `~/.config/containers/systemd/`, run `systemctl --user daemon-reload`, and keep both units disabled by default. VLR controls lifecycle explicitly.

If a local ComfyUI image is preferred, set `VLR_COMFYUI_IMAGE` and use the direct Podman runtime instead. Do not apply `HSA_OVERRIDE_GFX_VERSION` unless a real backend compatibility test demonstrates that it is necessary.
