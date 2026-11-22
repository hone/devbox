# System Specification: CI-Built Container Images & Renovate Dependency Automation

## 1. File Path Manifest
### Create
- `renovate.json`
- `.github/workflows/build.yml`
- `tests/verify_001_ci_images_and_renovate.py`

### Modify
- `devbox/mise.global.toml`
- `obsidian/mise.global.toml`
- `devbox/Containerfile`
- `obsidian/Containerfile`
- `devbox/distrobox.ini`
- `obsidian/distrobox.ini`
- `Justfile`

### Delete
- *(None)*

## 2. Public Contract & Internal Design

### Public Interfaces (Contract)
This repository is a GitOps container infrastructure repo (no compiled library crate); its public contracts are the declarative configuration schemas, OCI image coordinates, CI workflow interface, and host `Justfile` CLI surface.

#### 2.1 OCI Image Coordinates & Labels (`devbox/Containerfile`, `obsidian/Containerfile`)
- **Published images (public GHCR packages):**
  - `ghcr.io/hone/devbox:latest` and `ghcr.io/hone/devbox:sha-<short-sha>`
  - `ghcr.io/hone/obsidian:latest` and `ghcr.io/hone/obsidian:sha-<short-sha>`
- **Base image instruction format:**
  ```dockerfile
  FROM ghcr.io/ublue-os/fedora-toolbox:latest@sha256:<64-hex-digest>
  LABEL org.opencontainers.image.source="https://github.com/hone/devbox"
  ```
- **Optional BuildKit secret mount for `mise install`:**
  ```dockerfile
  RUN --mount=type=secret,id=github_token,required=false \
      if [ -f /run/secrets/github_token ]; then \
          export GITHUB_TOKEN="$(cat /run/secrets/github_token)"; \
      fi && \
      mise install
  ```

#### 2.2 Declarative Toolchain Pins (`devbox/mise.global.toml`, `obsidian/mise.global.toml`)
- Both files preserve `[settings]` (`color = true`, `experimental = true`).
- `[tools]` maps every tool to an explicit pinned version string (or inline table `{ version = "<pinned>", ... }`). No `"latest"` values are permitted.
- **Registry short-name normalization:**
  - `devbox/mise.global.toml`: `jj`, `node`, `opencode`, `rust`, `github-cli`, `antigravity-cli`, `helix`, `codex`, `cargo-release`, `heroku`.
  - `obsidian/mise.global.toml`: `node`, `opencode`, `rust`, `"npm:defuddle"` (retaining `depends = ["node"]`), `codex`, `helix`.

#### 2.3 Renovate Configuration Contract (`renovate.json`)
```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": [
    "config:recommended",
    "docker:pinDigests"
  ],
  "platformAutomerge": true,
  "automerge": true,
  "automergeType": "pr",
  "packageRules": [
    {
      "matchManagers": ["dockerfile"],
      "matchPackageNames": ["ghcr.io/ublue-os/fedora-toolbox"],
      "schedule": ["before 6am on monday"]
    }
  ]
}
```
- Uses Renovate's built-in `mise` manager (default-matches `**/mise{,.*}.toml`), `dockerfile` manager (default-matches `Containerfile`), and `github-actions` manager (default-matches `.github/workflows/*.yml`).
- `mise` tools remain ungrouped so a broken tool update isolates to its own PR while matching tools across `devbox/` and `obsidian/` naturally share one PR.

#### 2.4 GitHub Actions Workflow Contract (`.github/workflows/build.yml`)
- **Triggers:**
  - `pull_request` targeting `main`
  - `push` to `main`
  - `workflow_dispatch`
- **Permissions:** `contents: read`, `packages: write`
- **Job `build` (matrix `env: [devbox, obsidian]`):**
  - Check name per matrix entry (`build (devbox)`, `build (obsidian)`) serves as the required status check in the `main` GitHub Ruleset.
  - Step 1: `actions/checkout`
  - Step 2: `docker/setup-buildx-action`
  - Step 3: Build image with `docker/build-push-action`:
    - `context: ${{ matrix.env }}`, `file: ${{ matrix.env }}/Containerfile`
    - `platforms: linux/amd64`
    - `load: true`, `push: false` (loads the exact image locally before testing)
    - `tags`: `ghcr.io/hone/${{ matrix.env }}:latest` and `ghcr.io/hone/${{ matrix.env }}:sha-${{ ... }}` (7-char short SHA)
    - `labels`: `org.opencontainers.image.source=https://github.com/hone/devbox` and `org.opencontainers.image.revision=${{ github.sha }}`
    - `cache-from: type=gha,scope=${{ matrix.env }}`, `cache-to: type=gha,mode=max,scope=${{ matrix.env }}`
    - `secrets: |` passing `"github_token=${{ secrets.GITHUB_TOKEN }}"`
  - Step 4: In-container smoke test against `ghcr.io/hone/${{ matrix.env }}:latest`:
    - Verifies `/etc/mise/config.toml` exists and `/etc/mise/setup.sh` is executable (`-x`).
    - Verifies `mise ls --missing` produces empty output and `mise ls --current --json` reports every configured tool installed without broken paths.
    - For `devbox`: verifies `/usr/local/bin/docker` is executable (`-x`), and `pg_ctl --version` + `valkey-server --version` succeed.
  - Step 5 (gated strictly to `(github.event_name == 'push' && github.ref == 'refs/heads/main') || github.event_name == 'workflow_dispatch'`):
    - `docker/login-action` against `ghcr.io` using `github.actor` and `secrets.GITHUB_TOKEN`.
    - Push both tested tags (`:latest` and `:sha-<short>`) via `docker push`.

#### 2.5 Distrobox & Host `Justfile` CLI Contract (`devbox/distrobox.ini`, `obsidian/distrobox.ini`, `Justfile`)
- **`<env>/distrobox.ini`:**
  ```ini
  [<env>]
  image=ghcr.io/hone/<env>:latest
  pull=true
  replace=true
  additional_packages=""
  init_hooks="/etc/mise/setup.sh"
  ```
- **`Justfile` recipes (`default_env := 'devbox'`):**
  - `pull env=default_env`: `podman pull ghcr.io/hone/{{env}}:latest`
  - `create env=default_env`: runs `distrobox assemble create --file {{env}}/distrobox.ini --name {{env}}` (no local build prerequisite; relies on `pull=true` in `distrobox.ini`).
  - `rebuild env=default_env`: runs `distrobox assemble create --file {{env}}/distrobox.ini --replace --name {{env}}` (no local build prerequisite).
  - `build env=default_env`: local escape hatch — `podman build --pull -t {{env}}-base:latest {{env}}`.
  - `create-local env=default_env: (build env)`: creates container from `localhost/{{env}}-base:latest` using a `mktemp` copy of `{{env}}/distrobox.ini` with `image=` rewritten to `localhost/{{env}}-base:latest` and `pull=false`, cleaned up via `trap 'rm -f "$tmp"' EXIT`.
  - `rebuild-local env=default_env: (build env)`: same `mktemp` + `trap` local override with `--replace`.
  - `update env=default_env`: local uncached escape hatch — `podman build --no-cache -t {{env}}-base:latest {{env}}`.
  - Preserves existing `enter`, `rm`, `pg-start`, `pg-stop`, and `pg-status` recipes unchanged.

### Internal Module Design (Non-Contract Blueprint)
- **Seam & Dependency Classification:**
  - *In-process / local verification (`tests/verify_001_ci_images_and_renovate.py`):* Pure Python 3 stdlib (`tomllib`, `json`, `configparser`, `re`, `pathlib`, `subprocess`) parses every declarative artifact in the repo and enforces `INV-1` through `INV-9` offline inside `devbox` without requiring `podman`, `distrobox`, or third-party Python packages (`PyYAML` is not installed).
  - *External CI boundary (`.github/workflows/build.yml`):* GitHub Actions runners + BuildKit + GHCR execute real image builds, smoke tests, and registry publishes. No duplicate local shell build wrappers are introduced (passes Deletion Test).
  - *Host boundary (`Justfile` + `distrobox.ini`):* Thin recipes delegate directly to `podman` and `distrobox assemble`; local override logic uses a self-contained `mktemp` + `trap` recipe body rather than a separate helper script.

## 3. Invariants & Safety Constraints
- **INV-1 (No floating `"latest"` tool pins):** Every tool in `devbox/mise.global.toml` and `obsidian/mise.global.toml` specifies a concrete non-empty version string; `"latest"` does not appear as a tool version anywhere in either file.
- **INV-2 (Renovate-compatible `mise` keys):** Neither `mise.global.toml` uses explicit `aqua:` prefixes; registry-supported tools use short names (`antigravity-cli`, `helix`, `codex`, `cargo-release`, `heroku`, `jj`, `node`, `opencode`, `rust`, `github-cli`), and `"npm:defuddle"` preserves `depends = ["node"]`.
- **INV-3 (Digest-pinned Fedora base image & OCI source label):** Both `devbox/Containerfile` and `obsidian/Containerfile` start with `FROM ghcr.io/ublue-os/fedora-toolbox:latest@sha256:<64-lowercase-hex>` and declare `LABEL org.opencontainers.image.source="https://github.com/hone/devbox"`.
- **INV-4 (Optional non-leaking BuildKit secret):** Both `Containerfile`s run `mise install` with `RUN --mount=type=secret,id=github_token,required=false` and only export `GITHUB_TOKEN` inside that `RUN` layer when `/run/secrets/github_token` exists; no `GITHUB_TOKEN` appears in `ARG` or `ENV`.
- **INV-5 (Renovate automerge & base-image cadence):** `renovate.json` is valid JSON extending `config:recommended` and `docker:pinDigests`, sets `platformAutomerge: true`, `automerge: true`, `automergeType: "pr"`, includes a weekly `schedule` rule targeting `dockerfile` / `ghcr.io/ublue-os/fedora-toolbox`, and does not group `mise` tools into a single group.
- **INV-6 (CI matrix, smoke-test-before-push, and PR push isolation):** `.github/workflows/build.yml` triggers on `pull_request` (`main`), `push` (`main`), and `workflow_dispatch`; builds both `devbox` and `obsidian` for `linux/amd64` with `load: true`, `push: false`, and `github_token` secret; runs a smoke test verifying `mise ls --missing` is empty and `/etc/mise/setup.sh` is executable (plus `/usr/local/bin/docker`, `pg_ctl`, `valkey-server` for `devbox`); and gates `ghcr.io` login and `docker push` (`:latest` and `:sha-`) strictly to `main` pushes or `workflow_dispatch` (never `pull_request`).
- **INV-7 (Pull-first Distrobox manifests):** Both `devbox/distrobox.ini` and `obsidian/distrobox.ini` set `image=ghcr.io/hone/<env>:latest`, `pull=true`, `replace=true`, and `init_hooks="/etc/mise/setup.sh"`.
- **INV-8 (Pull-first `Justfile` & non-mutating local escape hatches):** `Justfile` defines `pull` (`podman pull ghcr.io/hone/{{env}}:latest`); `create` and `rebuild` do **not** depend on `(build env)`; `build`, `create-local`, `rebuild-local`, and `update` exist; `create-local` and `rebuild-local` depend on `(build env)`, rewrite `image=` to `localhost/{{env}}-base:latest` and `pull=` to `false` in a `mktemp` file cleaned up via `trap`, and never edit tracked `distrobox.ini` in place.
- **INV-9 (Preserved shell script validity):** `devbox/setup.sh`, `devbox/docker.sh`, and `obsidian/setup.sh` pass `bash -n` / `sh -n` syntax checks with zero errors.

## 4. Verification Targets
- **Contract Test Script (Stage 3):** `tests/verify_001_ci_images_and_renovate.py` (covers `INV-1` through `INV-9`).
- **Verification Command (inside `devbox`):** `python3 tests/verify_001_ci_images_and_renovate.py`
- **Post-Push Live Verification (External — GitHub / Host):**
  1. Push branch / PR and verify GitHub Actions `build (devbox)` and `build (obsidian)` succeed and do not push to GHCR on PR.
  2. Configure one-time GitHub repo settings (Renovate GitHub App, Allow auto-merge, auto-delete head branches, `main` Ruleset requiring `build (devbox)` and `build (obsidian)` with admin bypass).
  3. Merge to `main`, verify GHCR publish of `ghcr.io/hone/devbox:latest` and `ghcr.io/hone/obsidian:latest`, confirm Public visibility, and test `just pull && just rebuild` on the host.
