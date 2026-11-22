# Architecture

## Overview
This repository defines reproducible, disposable Distrobox development containers using a **CI-baked GitOps** model. System packages (`dnf`) and pinned language/CLI toolchains (`mise`) are built and smoke-tested in GitHub Actions on a digest-pinned Universal Blue base image (`ghcr.io/ublue-os/fedora-toolbox:latest@sha256:...`), published as public OCI images to GitHub Container Registry (`ghcr.io/hone/devbox:latest` and `ghcr.io/hone/obsidian:latest`), and pulled locally by `distrobox assemble`. Renovate keeps tool versions, base image digests, and GitHub Actions digests up to date via CI-gated automerge PRs.

## Directory & Component Map

| Path | Purpose |
|------|---------|
| [Justfile](../Justfile) | Host-side task runner for pull-first container lifecycle, local build escape hatches, and on-demand services (`default_env := 'devbox'`). |
| [devbox/](../devbox/) | Primary development container (`Containerfile`, `distrobox.ini`, `mise.global.toml`, `setup.sh`, `docker.sh`). |
| [obsidian/](../obsidian/) | Secondary container (`Containerfile`, `distrobox.ini`, `mise.global.toml`, `setup.sh`). |
| [.github/workflows/build.yml](../.github/workflows/build.yml) | Matrix CI workflow building, smoke-testing, and publishing `devbox` and `obsidian` images to GHCR. |
| [renovate.json](../renovate.json) | Renovate GitHub App config (`mise`, `dockerfile` digest pinning, GHA SHA pinning, PR platform automerge, weekly base-image cadence). |
| [tests/](../tests/) | Zero-dependency Python 3 stdlib contract verification scripts runnable inside `devbox`. |
| [docs/specs/](specs/) | Feature RFCs, interface specs, tasks, and small specs. |

## Core Design Constraints

1. **Pinned Toolchains & Base Images with Renovate Automation**
   - Every tool in `devbox/mise.global.toml` and `obsidian/mise.global.toml` is pinned to a concrete version (no `"latest"`), using `mise` registry short names where available so Renovate's built-in `mise` manager tracks them cleanly.
   - Both `Containerfile`s pin `ghcr.io/ublue-os/fedora-toolbox:latest@sha256:<digest>` (since uBlue publishes `:latest` only) and declare `org.opencontainers.image.source="https://github.com/hone/devbox"`.
   - Renovate opens ungrouped PRs for `mise` updates (isolating failures while combining matching tools across `devbox/` and `obsidian/`) and weekly PRs for base-image digest bumps, with `platformAutomerge` gated on CI smoke tests passing.

2. **Isolated System-Wide `mise` Paths & Optional BuildKit Secrets**
   - `Containerfile` sets `MISE_DATA_DIR=/usr/local/share/mise`, `MISE_CONFIG_DIR=/etc/mise`, and `MISE_CACHE_DIR=/usr/local/share/mise/cache`, bakes `mise.global.toml` to `/etc/mise/config.toml`, runs `mise install` with `RUN --mount=type=secret,id=github_token,required=false` (exporting `GITHUB_TOKEN` only when `/run/secrets/github_token` is non-empty, avoiding anonymous GitHub API rate limits in CI without leaking tokens into layers or breaking local `podman build`), and `chown -R 1000:1000` for UID `1000`.
   - Keeping `mise` state under `/usr/local/share/mise` and `/etc/mise` prevents collisions with the host's `$HOME` (which Distrobox mounts into the container).

3. **CI Smoke-Test-Before-Push & Serialized Publishing**
   - `.github/workflows/build.yml` builds `devbox` and `obsidian` (`linux/amd64`, GHA BuildKit cache, `load: true`, `push: false`), runs an in-container smoke test verifying `/etc/mise/setup.sh`, zero missing `mise` tools, all configured tools installed with valid on-disk paths (plus `docker`, `pg_ctl`, and `valkey-server` for `devbox`), and only pushes `:latest` + `:sha-<short>` to GHCR on `main` (`push` or `workflow_dispatch`).
   - Top-level `concurrency` cancels stale PR builds while queuing `main` publishes sequentially so `:latest` cannot race.

4. **Shell-Agnostic Shim Integration (`setup.sh`)**
   - `distrobox.ini` runs `init_hooks="/etc/mise/setup.sh"`.
   - `setup.sh` writes `~/.bashrc.d/mise.sh` (overwriting) and appends to `~/.config/nushell/env.nu` (guarded by `grep -q "$SHIMS_PATH"`), exporting `MISE_*`, `PGHOST="/tmp"` (`devbox`), and prepending `/usr/local/share/mise/shims` to `PATH`.

5. **On-Demand PostgreSQL (`devbox`)**
   - Installed via `dnf` (`postgresql-server`, `postgresql`) in `devbox/Containerfile` rather than `mise` to avoid compiling from source during image builds.
   - Managed from the host via `just pg-start`, `just pg-stop`, and `just pg-status`, storing cluster data in `~/.local/share/postgres/data`.
   - Sockets are placed in `/tmp` (`-o "-k /tmp"` and `unix_socket_directories = '/tmp'`, paired with `PGHOST="/tmp"` in `setup.sh`) to avoid container permission issues on `/var/run/postgresql`.

6. **Host Docker Forwarding (`devbox`)**
   - `devbox/docker.sh` is baked to `/usr/local/bin/docker` and delegates to `distrobox-host-exec docker "$@"`.

## Container Lifecycle (`Justfile`)

| Recipe | Action |
|--------|--------|
| `just pull [env]` | Pull `ghcr.io/hone/<env>:latest` via `podman pull`. |
| `just create [env]` | Run `distrobox assemble create` against `ghcr.io/hone/<env>:latest` (`pull=true`). |
| `just rebuild [env]` | Run `distrobox assemble create --replace` against `ghcr.io/hone/<env>:latest`. |
| `just build [env]` | Local escape hatch: build `localhost/<env>-base:latest` with `--pull`. |
| `just create-local [env]` | Local escape hatch: build locally and assemble using a temporary `mktemp` override (never mutates tracked `distrobox.ini`). |
| `just rebuild-local [env]` | Local escape hatch: build locally and replace container using a temporary `mktemp` override. |
| `just update [env]` | Local escape hatch: rebuild `localhost/<env>-base:latest` with `--no-cache`. |
| `just enter [env]` | Enter the container with `distrobox enter`. |
| `just rm [env]` | Remove the container via `distrobox assemble rm`. |
| `just pg-start` / `pg-stop` / `pg-status` | Initialize (if needed), start, stop, or inspect PostgreSQL inside `devbox`. |

## Future Ideas
*(Carried over from the retired `PLAN.md`; promote to `docs/specs/` when ready to design and implement.)*
- Explore persistent internal volumes if full image baking becomes a bottleneck for quick tool additions.
- Integrate dotfile symlinking (e.g., `.vimrc`) into `setup.sh`.
- Add support for project-specific `mise.toml` auto-install tests.
