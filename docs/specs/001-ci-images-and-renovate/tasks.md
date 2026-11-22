# Tasks: CI-Built Container Images & Renovate Dependency Automation

## Checklist

- [x] **Task 1: Pin `mise` tool versions and normalize keys**
  - **Files:** `devbox/mise.global.toml`, `obsidian/mise.global.toml`
  - **Done when:** `python3 tests/verify_001_ci_images_and_renovate.py Spec001ContractTests.test_inv1_no_floating_latest_tool_versions Spec001ContractTests.test_inv2_renovate_compatible_mise_keys` passes.

- [x] **Task 2: Pin `fedora-toolbox` base image digest, add OCI source label, and mount optional BuildKit `github_token` secret**
  - **Files:** `devbox/Containerfile`, `obsidian/Containerfile`
  - **Done when:** `python3 tests/verify_001_ci_images_and_renovate.py Spec001ContractTests.test_inv3_base_image_pinned_and_oci_source_label Spec001ContractTests.test_inv4_optional_non_leaking_buildkit_secret` passes.

- [x] **Task 3: Add `renovate.json` configuration**
  - **Files:** `renovate.json`
  - **Done when:** `python3 tests/verify_001_ci_images_and_renovate.py Spec001ContractTests.test_inv5_renovate_config_contract` passes.

- [x] **Task 4: Add GitHub Actions build, smoke-test, and GHCR publish workflow**
  - **Files:** `.github/workflows/build.yml`
  - **Done when:** `python3 tests/verify_001_ci_images_and_renovate.py Spec001ContractTests.test_inv6_ci_workflow_contract` passes.

- [x] **Task 5: Switch Distrobox manifests and `Justfile` to pull-first with non-mutating local escape hatches**
  - **Files:** `devbox/distrobox.ini`, `obsidian/distrobox.ini`, `Justfile`
  - **Done when:** `python3 tests/verify_001_ci_images_and_renovate.py Spec001ContractTests.test_inv7_pull_first_distrobox_manifests Spec001ContractTests.test_inv8_pull_first_justfile_and_local_escape_hatches` passes.

- [x] **Task 6: Full Feature Verification**
  - **Files:** `devbox/mise.global.toml`, `obsidian/mise.global.toml`, `devbox/Containerfile`, `obsidian/Containerfile`, `renovate.json`, `.github/workflows/build.yml`, `devbox/distrobox.ini`, `obsidian/distrobox.ini`, `Justfile`
  - **Done when:** `python3 tests/verify_001_ci_images_and_renovate.py` passes all 9 contract tests with zero failures.
