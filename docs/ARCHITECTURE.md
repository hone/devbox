# Architecture

## Overview
This repository defines reproducible, disposable Distrobox development containers using a **baked-image GitOps** model. System packages (`dnf`) and global language/CLI toolchains (`mise`) are baked into local Podman images (`localhost/<env>-base:latest`), and `distrobox assemble` creates containers from those images.

## Directory & Component Map

| Path | Purpose |
|------|---------|
| [Justfile](../Justfile) | Host-side task runner for container lifecycle and on-demand services (`default_env := 'devbox'`). |
| [devbox/](../devbox/) | Primary development container (`Containerfile`, `distrobox.ini`, `mise.global.toml`, `setup.sh`, `docker.sh`). |
| [obsidian/](../obsidian/) | Secondary container (`Containerfile`, `distrobox.ini`, `mise.global.toml`, `setup.sh`). |
| [docs/specs/](specs/) | Feature RFCs, interface specs, tasks, and small specs. |

## Core Design Constraints

1. **Isolated System-Wide `mise` Paths**
   - `Containerfile` sets `MISE_DATA_DIR=/usr/local/share/mise`, `MISE_CONFIG_DIR=/etc/mise`, and `MISE_CACHE_DIR=/usr/local/share/mise/cache`, bakes `mise.global.toml` to `/etc/mise/config.toml`, runs `mise install`, and `chown -R 1000:1000` so UID `1000` can install or update tools without permission issues.
   - Keeping `mise` state under `/usr/local/share/mise` and `/etc/mise` prevents collisions with the host's `$HOME` (which Distrobox mounts into the container).

2. **Shell-Agnostic Shim Integration (`setup.sh`)**
   - `distrobox.ini` runs `init_hooks="/etc/mise/setup.sh"`.
   - `setup.sh` writes `~/.bashrc.d/mise.sh` (overwriting) and appends to `~/.config/nushell/env.nu` (guarded by `grep -q "$SHIMS_PATH"`), exporting `MISE_*`, `PGHOST="/tmp"`, and prepending `/usr/local/share/mise/shims` to `PATH`.

3. **On-Demand PostgreSQL (`devbox`)**
   - Installed via `dnf` (`postgresql-server`, `postgresql`) in `devbox/Containerfile` rather than `mise` to avoid compiling from source during image builds.
   - Managed from the host via `just pg-start`, `just pg-stop`, and `just pg-status`, storing cluster data in `~/.local/share/postgres/data`.
   - Sockets are placed in `/tmp` (`-o "-k /tmp"` and `unix_socket_directories = '/tmp'`, paired with `PGHOST="/tmp"` in `setup.sh`) to avoid container permission issues on `/var/run/postgresql`.

4. **Host Docker Forwarding (`devbox`)**
   - `devbox/docker.sh` is baked to `/usr/local/bin/docker` and delegates to `distrobox-host-exec docker "$@"`.

## Container Lifecycle (`Justfile`)

| Recipe | Action |
|--------|--------|
| `just build [env]` | Build `localhost/<env>-base:latest` with `--pull`. |
| `just create [env]` | Build image and run `distrobox assemble create`. |
| `just rebuild [env]` | Build image and run `distrobox assemble create --replace`. |
| `just enter [env]` | Enter the container with `distrobox enter`. |
| `just rm [env]` | Remove the container via `distrobox assemble rm`. |
| `just update [env]` | Rebuild image with `--no-cache`. |
| `just pg-start` / `pg-stop` / `pg-status` | Initialize (if needed), start, stop, or inspect PostgreSQL inside `devbox`. |

## Future Ideas
*(Carried over from the retired `PLAN.md`; promote to `docs/specs/` when ready to design and implement.)*
- Explore persistent internal volumes if full image baking becomes a bottleneck for quick tool additions.
- Integrate dotfile symlinking (e.g., `.vimrc`) into `setup.sh`.
- Add support for project-specific `mise.toml` auto-install tests.
