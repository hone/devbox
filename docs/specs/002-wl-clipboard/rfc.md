---
status: idea
updated: 2026-11-22
---

# RFC: Wayland Clipboard Support (`wl-clipboard`)

## 1. Problem Statement
When running `agy` (Antigravity CLI) inside Distrobox on a Wayland host (`WAYLAND_DISPLAY=wayland-0`, `DISPLAY` unset), pasting images from the clipboard fails because `agy` relies on `wl-paste` (from `wl-clipboard`) on Wayland and falls back to `xclip` on X11. Neither `wl-clipboard` nor `xclip` is currently baked into `devbox` or `obsidian`.

## 2. Goals & Non-Goals
### Goals
- Enable seamless clipboard image pasting in `agy` (and general CLI clipboard integration) inside container environments on Wayland hosts.
- Verify clipboard tooling is installed during CI smoke testing.

### Non-Goals
- Full GUI / Wayland compositor setup inside the container (relies on Distrobox's existing Wayland socket forwarding).

## 3. Proposal
*(Parked idea — refine scope and trade-offs in a fresh session before promoting to `rfc` or a Small Spec.)*
- Add `wl-clipboard` to the `dnf install` package list in `devbox/Containerfile` (and optionally `obsidian/Containerfile`).
- Optionally add a CI smoke-test assertion (`wl-paste --version`) in `.github/workflows/build.yml`.

## 4. Explored Alternatives & Trade-offs
*(To be completed when promoted from `idea`.)*

## 5. Open Questions & Risks
- **Open Question:** Should `wl-clipboard` be installed in `devbox` only, or in both `devbox` and `obsidian`?
- **Open Question:** Should `xclip` also be installed as an X11 / `ssh -X` fallback, or keep it Wayland-only (`wl-clipboard`)?
- **Open Question:** Since this touches 1–2 files (`Containerfile` + optional smoke test), should it be executed as a Small Spec (`002-wl-clipboard.md`) instead of a full 4-stage feature folder?
- **Risk:** Verify Distrobox forwards `$WAYLAND_DISPLAY` and `$XDG_RUNTIME_DIR` socket permissions cleanly so `wl-paste` inside the container can read the host clipboard (test live on host after image build).
