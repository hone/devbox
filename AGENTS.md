# Repository Guidelines

## Overview
GitOps-managed development container definitions built in **GitHub Actions** (published to GHCR), kept fresh with **Renovate**, and assembled locally with **Podman**, **Distrobox** (`distrobox assemble`), **mise**, and **Just**. Containers are treated as disposable ("cattle") with configuration version-controlled here.

## Environment Layout
- `Justfile` — Host-side lifecycle & service recipes (`pull`, `create`, `rebuild`, `build`, `create-local`, `rebuild-local`, `enter`, `rm`, `update`, `pg-start`, `pg-stop`, `pg-status`). Default `env=devbox`.
- `devbox/` — Primary development environment (`Containerfile`, `distrobox.ini`, `mise.global.toml`, `setup.sh`, `docker.sh`).
- `obsidian/` — Secondary environment (`Containerfile`, `distrobox.ini`, `mise.global.toml`, `setup.sh`).
- `.github/workflows/build.yml` — Matrix CI workflow building, smoke-testing, and publishing `ghcr.io/hone/devbox` and `ghcr.io/hone/obsidian`.
- `renovate.json` — Renovate GitHub App configuration (pinned `mise` tools, digest-pinned base images, SHA-pinned GitHub Actions, PR automerge).
- `tests/` — Python 3 stdlib contract verification scripts.

## Development Workflow
- **VCS:** Colocated Jujutsu (`jj`) + Git repository. Keep `.gwendolyn/` ignored in `.gitignore`.
- **Spec-Driven Development:** Use `docs/specs/` for features (`NNN-feature-name/` with `rfc.md`, `spec.md`, `tasks.md`) and small internal changes (`NNN-name.md`), and keep `docs/ARCHITECTURE.md` up to date when architecture changes.
- **Verification:**
  - Contract tests: `python3 tests/verify_001_ci_images_and_renovate.py` and `python3 tests/verify_002_wl_clipboard.py` (includes `bash -n` / `sh -n` checks on `*/setup.sh` and `*/docker.sh`).
  - Containerfiles & `mise.global.toml`: verified in CI via `.github/workflows/build.yml`, or locally on the host with `just build <env>` / `just rebuild-local <env>` when Podman is available.
  - Note that `just` / `podman` / `distrobox` manage host-side containers and may not be runnable from inside a sandboxed container session.
