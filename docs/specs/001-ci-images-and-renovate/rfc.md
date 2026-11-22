---
status: done
updated: 2026-11-20
---

# RFC: CI-Built Container Images & Renovate Dependency Automation

## 1. Problem Statement
Both `devbox` and `obsidian` currently bake toolchains into local Podman images using `"latest"` in `mise.global.toml` and `:latest` for `ghcr.io/ublue-os/fedora-toolbox`, built on-demand on the host via `just build` / `just update`.

This creates three friction points:
1. **Non-reproducible builds:** Rebuilding on a different day silently pulls newer tool or OS versions with no version history, diff, or pre-flight validation.
2. **Slow local rebuilds:** Updating tools requires running full image builds on the host (including compiling tools like `cargo:cargo-release` from source).
3. **Manual freshness:** Keeping toolchains and base images current depends on remembering to run `just update` locally, with no automated signal if an upstream release breaks installation.

## 2. Goals & Non-Goals
### Goals
- Pin every tool in `devbox/mise.global.toml` and `obsidian/mise.global.toml` to an explicit version (removing all `"latest"` entries) and adopt `mise` registry short names where supported.
- Pin the `ghcr.io/ublue-os/fedora-toolbox` base image in both `Containerfile`s to `:latest` with an immutable digest (`:latest@sha256:...`).
- Automate dependency updates for both `mise` tools and base images via the hosted **Renovate GitHub App**, with CI-gated PR automerge.
- Build and smoke-test both images in **GitHub Actions** on pull requests (no push), and publish separate public OCI images (`ghcr.io/hone/devbox` and `ghcr.io/hone/obsidian`) to GHCR on push to `main` (and manual dispatch).
- Switch default host lifecycle commands (`just create`, `just rebuild`) to pull prebuilt GHCR images for `distrobox assemble`, while retaining a local build/rebuild escape hatch for iterating on `Containerfile` changes before pushing.

### Non-Goals
- Pinning individual `dnf` RPM package versions or the `mise` RPM version inside the `Containerfile`s (Fedora package updates remain resolved at image build time).
- Multi-architecture image builds (`linux/arm64`); target architecture remains `linux/amd64` only.
- Private registry authentication or secrets inside container images (`hone/devbox` is public and contains no secrets).
- Changing `setup.sh` shell integrations or PostgreSQL lifecycle recipes.
- Automatic host-side container replacement (pulling and running `just rebuild` remains an explicit host command).

## 3. Proposal

### 3.1 Declarative Version Pinning (`mise` & Base Images)
- Replace all `"latest"` entries in `devbox/mise.global.toml` and `obsidian/mise.global.toml` with concrete versions.
- Convert explicit backend entries that exist as first-class `mise` registry short names (`antigravity-cli`, `helix`, `codex`, `cargo-release`, `heroku`) to short names so Renovate's built-in `mise` manager tracks them cleanly without custom regex rules. (Switching `cargo:cargo-release` to `cargo-release` also uses prebuilt GitHub release binaries via `github:crate-ci/cargo-release`, speeding up CI builds.) Keep `"npm:defuddle"` explicit since it is not in the `mise` registry (`npm:` is natively supported by Renovate's `mise` manager).
- Pin both `Containerfile`s to `ghcr.io/ublue-os/fedora-toolbox:latest@sha256:<digest>` (since `ublue-os/fedora-toolbox` only publishes `:latest`) and add OCI `org.opencontainers.image.source` labels so GHCR associates both packages with `hone/devbox`.

### 3.2 Renovate Automation (`renovate.json` + Hosted GitHub App)
- Install the hosted **Renovate GitHub App** on `hone/devbox` and configure `renovate.json` extending `config:recommended` and `docker:pinDigests`.
- Use Renovate's built-in `mise` manager (default-matches `**/mise{,.*}.toml`) and `dockerfile` manager (default-matches `Containerfile`).
- Enable PR-based platform automerge (`automerge: true`, `automergeType: "pr"`, `platformAutomerge: true`) across all update types (digests, patches, minors, majors). Because the prior workflow tracked `"latest"`, CI-validated automerge is strictly safer: green builds merge and publish automatically, while a broken upstream release stays on an open red PR without touching `main` or GHCR.
- Keep `mise` tool updates **ungrouped** so a single broken tool does not block unrelated healthy updates (Renovate naturally combines identical package bumps across `devbox/` and `obsidian/` into one PR).
- Put `fedora-toolbox` base-image updates on a **weekly schedule** so uBlue's daily rebuilds do not churn the repo every day.

### 3.3 GitHub Actions Build, Smoke-Test & Publish Pipeline
- A single workflow with a matrix over `devbox` and `obsidian`:
  - **On Pull Requests (including Renovate PRs):** Build each image using BuildKit caching (GitHub Actions cache) and pass `GITHUB_TOKEN` as a BuildKit secret into the `mise install` layer to avoid anonymous GitHub API rate limits without embedding any token in image layers. Run an in-container smoke test confirming every configured tool resolves and executes cleanly. Do **not** push to GHCR.
  - **On Push to `main` & `workflow_dispatch`:** Build, smoke-test, and push to separate public GHCR packages:
    - `ghcr.io/hone/devbox:latest` (+ immutable `sha-<short>` tag)
    - `ghcr.io/hone/obsidian:latest` (+ immutable `sha-<short>` tag)
- **One-Time GitHub Repository Setup (Manual Prerequisite):**
  1. Install the Renovate GitHub App on `hone/devbox`.
  2. Enable **Allow auto-merge** and **Automatically delete head branches** in repository settings.
  3. Add a `main` branch Ruleset requiring the CI build/smoke status check(s) (with Repository Admin bypass enabled so direct pushes remain possible, and *without* requiring branches to be strictly up-to-date on every merge to avoid $O(N^2)$ rebase cascades).
  4. Confirm both GHCR packages (`devbox`, `obsidian`) are set to **Public** visibility after the first publish.

### 3.4 Pull-First Distrobox & Host `Justfile` Ergonomics
- Update `devbox/distrobox.ini` and `obsidian/distrobox.ini` to pull from `ghcr.io/hone/devbox:latest` and `ghcr.io/hone/obsidian:latest` with `pull=true`.
- Update `Justfile` so default recipes (`just create`, `just rebuild`, plus an explicit `just pull`) pull from GHCR and run `distrobox assemble` without local image building.
- Retain local escape-hatch recipes (`just build`, `just rebuild-local`, `just update`) that build `localhost/<env>-base:latest` locally and assemble a container against that local image without requiring edits to tracked `distrobox.ini` files.

## 4. Explored Alternatives & Trade-offs
| Alternative | Trade-offs | Decision |
| :--- | :--- | :--- |
| **Renovate GitHub App** vs. self-hosted GHA Renovate workflow | GitHub App requires zero runner maintenance/PAT management and integrates natively with GitHub auto-merge; self-hosted gives arbitrary plugin execution but adds cron/token overhead. | **Selected: Renovate GitHub App** |
| **Separate GHCR packages** (`ghcr.io/hone/devbox`, `ghcr.io/hone/obsidian`) vs. single package with env tags | Separate packages give each Distrobox environment its own clean OCI repository, tags, and visibility/retention lifecycle; single package mixes unrelated tag histories. | **Selected: Separate packages** |
| **`automergeType: "pr"`** + GitHub Ruleset vs. `automergeType: "branch"` | `"pr"` uses GitHub native auto-merge immediately on green CI and leaves a clean PR audit trail; `"branch"` avoids PRs unless failing but relies on Renovate polling lag and conflicts with PR-based branch rules. | **Selected: `automergeType: "pr"`** |
| **Ungrouped `mise` PRs + weekly base image** vs. single weekly grouped PR | Ungrouped isolates failures so one bad release never blocks other updates, while weekly base-image scheduling avoids daily uBlue churn; single weekly mega-PR minimizes git log volume but shares blast radius. | **Selected: Ungrouped tools + weekly base image** |
| **`:latest@sha256:...`** (digest-pinned rolling tag) vs. switching to `registry.fedoraproject.org/fedora-toolbox:<release>@sha256:...` | Keeping uBlue's `fedora-toolbox:latest@sha256:...` preserves Universal Blue's Distrobox-ready base and still pins every build to an immutable digest updated weekly by Renovate; upstream Fedora requires re-adding uBlue's packages. | **Selected: `fedora-toolbox:latest@sha256:...`** |

## 5. Open Questions & Risks
- **Open Questions:** None blocking. Exact current tool versions and the current Fedora release tag + digest for `ghcr.io/ublue-os/fedora-toolbox` will be resolved during Stage 2/4.
- **Risk — GitHub API rate limits during CI `mise install`:** Unauthenticated GHA runner IPs share a 60 req/hr GitHub API limit that can break `aqua:`/`github:` tool downloads.
  - *Mitigation:* Mount `GITHUB_TOKEN` as an ephemeral BuildKit secret (`--mount=type=secret`) during `mise install` in CI so requests are authenticated while keeping secrets out of the built image.
- **Risk — Renovate's bundled `mise` registry lags behind upstream for newer tools (e.g., `antigravity-cli`, `opencode`):** If Renovate's built-in registry does not yet know a short name, Renovate could skip tracking that tool.
  - *Mitigation:* Verify every tool appears in Renovate's Dependency Dashboard after onboarding; add a targeted `customManagers` or `packageRules` entry only if any specific tool is missed.
- **Risk — GHCR package defaults to Private on first push:** Unauthenticated `podman pull` / `distrobox assemble` on the host would fail with `unauthorized`.
  - *Mitigation:* Include `org.opencontainers.image.source` OCI labels and verify/toggle package visibility to Public in GitHub Packages settings on initial rollout.
- **Risk — GitHub auto-merge merges before CI checks run if Ruleset is missing:** With `platformAutomerge: true` and no required status checks on `main`, GitHub can merge a PR immediately before GHA finishes.
  - *Mitigation:* Configure the `main` branch Ruleset requiring the CI check job(s) as part of onboarding before letting Renovate automerge PRs.
- **Risk — Local escape hatch mutating tracked `distrobox.ini`:** Switching between GHCR and local builds could accidentally dirty git working state.
  - *Mitigation:* Stage 2 (`spec.md`) will ensure local escape-hatch recipes pass the local image override cleanly (e.g., temporary ini or `distrobox create` flags) without modifying tracked `distrobox.ini`.
