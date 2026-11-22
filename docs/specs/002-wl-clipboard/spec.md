# System Specification: Wayland Clipboard Support (`wl-clipboard`)

## 1. File Path Manifest
### Create
- `tests/verify_002_wl_clipboard.py`

### Modify
- `devbox/Containerfile`
- `obsidian/Containerfile`
- `.github/workflows/build.yml`

### Delete
- *(None)*

## 2. Public Contract & Internal Design

### Public Interfaces (Contract)
This repository is a GitOps container infrastructure repo; its public contracts for this feature are the baked container system packages and the CI image smoke-test assertions.

#### 2.1 Container System Packages (`devbox/Containerfile`, `obsidian/Containerfile`)
- Both `Containerfile`s append `wl-clipboard` to their existing single `RUN ... dnf install -y ... && dnf clean all` instruction:
  - `devbox/Containerfile`: adds `wl-clipboard` alongside existing system dependencies (`bubblewrap`, `git`, `mise`, `postgresql-server`, `postgresql`, `valkey`, etc.).
  - `obsidian/Containerfile`: adds `wl-clipboard` alongside existing system dependencies (`bubblewrap`, `git`, `mise`, etc.).
- No additional `RUN dnf install` layer is added.
- Neither image installs X11 clipboard utilities (`xclip`, `xsel`) or adds `distrobox-host-exec` wrappers for `wl-copy` / `wl-paste`.

#### 2.2 CI Smoke-Test Contract (`.github/workflows/build.yml`)
- Inside the `Smoke test image` step (`docker run --rm "ghcr.io/hone/${{ matrix.env }}:latest" bash -ec '...'`), add unconditional assertions covering both `devbox` and `obsidian`:
  ```bash
  wl-paste --version
  wl-copy --version
  ```
- Both assertions execute outside the `if [ "${{ matrix.env }}" = "devbox" ]` conditional and strictly before `docker/login-action` and `docker push`.
- Both flags (`--version`) print version information and `exit(0)` during `getopt_long()` parsing before touching `WAYLAND_DISPLAY`, ensuring deterministic headless execution in GitHub Actions.

### Internal Module Design (Non-Contract Blueprint)
- **Seam & Dependency Classification:**
  - *In-process / local verification (`tests/verify_002_wl_clipboard.py`):* Pure Python 3 stdlib (`re`, `pathlib`, `unittest`) parses both `Containerfile`s and `.github/workflows/build.yml` offline inside `devbox` to enforce `INV-1` through `INV-3` without requiring `podman`, `distrobox`, or third-party packages.
  - *External CI boundary (`.github/workflows/build.yml`):* GitHub Actions builds real images and executes `wl-paste --version` and `wl-copy --version` inside both built containers prior to GHCR push.
  - *Host Wayland boundary:* Relies directly on Distrobox's existing forwarding of `WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR`, and `/run/user/1000/wayland-0` (no custom wrapper scripts; passes the Deletion Test).

## 3. Invariants & Safety Constraints
- **INV-1 (Wayland clipboard package baked into both images):** Both `devbox/Containerfile` and `obsidian/Containerfile` include `wl-clipboard` as a discrete package token inside their single `dnf install -y` instruction (before `dnf clean all`), without introducing a second `RUN dnf install` layer.
- **INV-2 (Wayland-only scope, no X11 fallbacks or host shims):** Neither `devbox/Containerfile` nor `obsidian/Containerfile` installs `xclip` or `xsel`, and neither `devbox/` nor `obsidian/` adds a `wl-copy` or `wl-paste` `distrobox-host-exec` wrapper script.
- **INV-3 (Headless CI smoke test across both environments before push):** `.github/workflows/build.yml` runs both `wl-paste --version` and `wl-copy --version` inside the `Smoke test image` container script, outside the `devbox`-only `if` block (so both `devbox` and `obsidian` execute them), and strictly before GHCR login (`docker/login-action`) and `docker push`.
- **INV-4 (Spec `001` regression safety):** All existing contract assertions in `tests/verify_001_ci_images_and_renovate.py` continue to pass unchanged.

## 4. Verification Targets
- **Contract Test Script (Stage 3):** `tests/verify_002_wl_clipboard.py` (covers `INV-1` through `INV-3`).
- **Regression Test Script:** `tests/verify_001_ci_images_and_renovate.py` (covers `INV-4`).
- **Verification Commands (inside `devbox`):**
  - `python3 tests/verify_002_wl_clipboard.py`
  - `python3 tests/verify_001_ci_images_and_renovate.py`
- **Post-Push Live Verification (External — GitHub / Host):**
  1. Push changes and verify GitHub Actions `build (devbox)` and `build (obsidian)` succeed, including `wl-paste --version` and `wl-copy --version` smoke tests.
  2. Pull and rebuild on the host (`just pull devbox && just rebuild devbox`, and `obsidian` as desired) and verify `wl-paste --list-types` and `agy` clipboard image pasting work live on GNOME/Wayland.
