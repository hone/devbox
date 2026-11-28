---
status: done
updated: 2026-11-27
---

# Small Spec: Host Podman Forwarding (`devbox`)

## 1. Intent & Scope
Mirror the existing host Docker forwarding shim (`devbox/docker.sh`) for Podman so `podman` invocations inside the `devbox` container delegate cleanly to the host Podman binary via `distrobox-host-exec`.

This change is `devbox`-only (`obsidian` is untouched) and introduces no new public interfaces:
- Core implementation (already drafted in working copy): `devbox/podman.sh`, `devbox/Containerfile`.
- CI smoke-test parity & regression coverage: `.github/workflows/build.yml` (`devbox`-gated smoke check) and `tests/verify_003_podman_host_exec.py`.
- Living documentation updates at completion: `docs/ARCHITECTURE.md` and `AGENTS.md`.

## 2. Invariants & Guardrails
- **INV-1 (Valid POSIX Host-Exec Shim):** `devbox/podman.sh` starts with `#!/bin/sh`, passes `sh -n`, and forwards all arguments via `exec distrobox-host-exec podman "$@"`.
- **INV-2 (Baked Executable in `devbox` Only):** `devbox/Containerfile` copies `podman.sh` to `/usr/local/bin/podman` and marks it executable (`chmod +x /usr/local/bin/podman`), preserving existing `docker` forwarding and leaving `obsidian/` untouched (no `obsidian/podman.sh` and no `/usr/local/bin/podman` in `obsidian/Containerfile`).
- **INV-3 (CI Smoke-Test Parity):** `.github/workflows/build.yml` checks `test -x /usr/local/bin/podman` inside the `devbox`-gated block of the `Smoke test image` step, strictly before GHCR login and `docker push`.

## 3. Tasks & Verification
- [x] **Task 1: Verify `devbox/podman.sh` & `devbox/Containerfile` and add CI smoke check**
  - **Files:** `devbox/podman.sh`, `devbox/Containerfile`, `.github/workflows/build.yml`
  - **Done when:** `sh -n devbox/podman.sh` passes, `devbox/Containerfile` bakes and `chmod +x`s `/usr/local/bin/podman`, and `.github/workflows/build.yml` runs `test -x /usr/local/bin/podman` inside the `devbox` smoke-test branch.
- [x] **Task 2: Add regression contract tests and sync living docs**
  - **Files:** `tests/verify_003_podman_host_exec.py`, `docs/ARCHITECTURE.md`, `AGENTS.md`
  - **Done when:** `python3 -B -m unittest discover -s tests -p 'verify_*.py' -v` passes with `INV-1`–`INV-3` covered, and `docs/ARCHITECTURE.md` + `AGENTS.md` reflect host `podman` forwarding.

## 4. Gate & Completion
- Confirm scope, invariants, and verification targets (`c/d?`) before changing `status: implementing`.
- Before setting `status: done`: confirm regression coverage for each `INV-n`, run `python3 -B -m unittest discover -s tests -p 'verify_*.py' -v`, present a **3–5 bullet Comprehension Brief**, pause for Pre-Review `c/d?`, and run `code-review`.
