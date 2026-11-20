# Repository Guidelines

## Overview
GitOps-managed development container definitions built with **Podman**, **Distrobox** (`distrobox assemble`), **mise**, and **Just**. Containers are treated as disposable ("cattle") with configuration version-controlled here.

## Environment Layout
- `Justfile` — Host-side lifecycle & service recipes (`build`, `create`, `rebuild`, `enter`, `rm`, `update`, `pg-start`, `pg-stop`, `pg-status`). Default `env=devbox`.
- `devbox/` — Primary development environment (`Containerfile`, `distrobox.ini`, `mise.global.toml`, `setup.sh`, `docker.sh`).
- `obsidian/` — Secondary environment (`Containerfile`, `distrobox.ini`, `mise.global.toml`, `setup.sh`).

## Development Workflow
- **VCS:** Colocated Jujutsu (`jj`) + Git repository. Keep `.gwendolyn/` ignored in `.gitignore`.
- **Spec-Driven Development:** Use `docs/specs/` for features (`NNN-feature-name/` with `rfc.md`, `spec.md`, `tasks.md`) and small internal changes (`NNN-name.md`), and keep `docs/ARCHITECTURE.md` up to date when architecture changes.
- **Verification:**
  - Shell scripts (`*/setup.sh`, `*/docker.sh`): verify syntax with `bash -n` / `sh -n`.
  - Containerfiles & `mise.global.toml`: verify with `just build <env>` (or `just rebuild <env>`) when Podman is available on the host.
  - Note that `just` / `podman` / `distrobox` manage host-side containers and may not be runnable from inside a sandboxed container session.
