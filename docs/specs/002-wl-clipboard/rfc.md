---
status: done
updated: 2026-11-22
---

# RFC: Wayland Clipboard Support (`wl-clipboard`)

## 1. Problem Statement
When running inside Distrobox containers on a Wayland host (`WAYLAND_DISPLAY=wayland-0`, `XDG_RUNTIME_DIR=/run/user/1000`), Distrobox already forwards the host Wayland socket (`/run/user/1000/wayland-0`) into the container, but neither `devbox` nor `obsidian` ships `wl-clipboard`.

As a result:
- `agy` (Antigravity CLI, installed in `devbox`) cannot paste clipboard images on Wayland because it shells out to `wl-paste`.
- Wayland-aware CLI tools shared across both `devbox` and `obsidian` (`helix`, `opencode`, `codex`) lack native `wl-copy` / `wl-paste` clipboard integration.

## 2. Goals & Non-Goals
### Goals
- Bake `wl-clipboard` (`wl-copy` and `wl-paste`) via `dnf` into both `devbox` and `obsidian` container images.
- Verify both `wl-paste` and `wl-copy` are installed and executable during CI smoke testing in `.github/workflows/build.yml` prior to publishing to GHCR.
- Lock the container and CI workflow contract with zero-dependency Python 3 stdlib tests (`tests/verify_002_wl_clipboard.py`).

### Non-Goals
- X11 / `ssh -X` clipboard fallbacks (`xclip`, `xsel`) — the host runs pure Wayland, and excluding X11 utilities keeps both images lean.
- Host-side `distrobox-host-exec` wrapper scripts — baking `wl-clipboard` inside the containers avoids layering packages on the immutable host and relies directly on Distrobox's Wayland socket forwarding.
- Background clipboard watching (`wl-paste --watch`) — GNOME/Mutter intentionally does not implement `wlr-data-control` or `ext-data-control`.
- Pinning the RPM version of `wl-clipboard` (consistent with Spec `001`: Fedora `dnf` packages resolve at image build time).
- Full GUI / Wayland compositor setup inside the containers.

## 3. Proposal
1. **Container Images (`devbox/Containerfile`, `obsidian/Containerfile`):** Add `wl-clipboard` to the existing `dnf install -y` system dependency layer in both `Containerfile`s (no additional layers or host shims).
2. **CI Smoke Testing (`.github/workflows/build.yml`):** Add `wl-paste --version` and `wl-copy --version` assertions to the matrix smoke test so both `devbox` and `obsidian` verify clipboard binaries before pushing to GHCR.
3. **Contract Verification (`tests/verify_002_wl_clipboard.py`):** Add a stdlib-only Python `unittest` suite verifying both `Containerfile`s install `wl-clipboard` (without `xclip`/`xsel`) and `.github/workflows/build.yml` smoke-tests `wl-paste` and `wl-copy` for both matrix environments prior to GHCR login/push.

## 4. Explored Alternatives & Trade-offs
| Alternative | Trade-offs | Decision |
| :--- | :--- | :--- |
| **Both `devbox` and `obsidian`** vs. `devbox`-only | `obsidian` omits `agy` but includes `helix`, `opencode`, and `codex`, all of which use `wl-copy`/`wl-paste` on Wayland; `wl-clipboard` is tiny and keeps both environments consistent. | **Selected: Both `devbox` and `obsidian`** |
| **Bake `wl-clipboard` inside containers** vs. `distrobox-host-exec` wrapper | Baking keeps containers self-contained with zero immutable-host package layering, communicating directly over Distrobox's forwarded `/run/user/1000/wayland-0` socket; host-exec would couple containers to host-installed packages and add `host-spawn` overhead. | **Selected: Bake inside containers** |
| **Wayland-only (`wl-clipboard`)** vs. `wl-clipboard` + `xclip` | Wayland-only matches the host session and avoids pulling X11 client dependencies; `xclip` adds X11/`ssh -X` fallback at the cost of extra packages not needed today. | **Selected: Wayland-only (`wl-clipboard`)** |

## 5. Open Questions & Risks
- **Open Questions:** None blocking.
- **Risk — GNOME/Mutter focus fallback for `wl-paste`:** Mutter intentionally does not implement `wlr-data-control` or `ext-data-control`, so `wl-paste` briefly spawns an invisible Wayland surface to borrow focus from the active terminal.
  - *Mitigation:* One-shot `wl-paste` from a focused terminal (the code path `agy` and `helix` use) works on Mutter; verify live image pasting in `devbox` after rebuilding from GHCR, and keep background `wl-paste --watch` explicitly out of scope.
- **Risk — Renovate advancing `main` concurrently:** Automated dependency PRs merge to `main` whenever CI passes.
  - *Mitigation:* Run `jj git fetch` before editing/rebasing so changes apply cleanly atop the latest `main@origin`.
