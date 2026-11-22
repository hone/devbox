# Implementation Tasks: Wayland Clipboard Support (`wl-clipboard`)

- [x] **Task 1:** Add `wl-clipboard` to the existing `dnf install -y` system dependency layer in `devbox/Containerfile` and `obsidian/Containerfile`.
  - **Verify:** `python3 -m unittest tests.verify_002_wl_clipboard.Spec002ContractTests.test_inv1_wl_clipboard_baked_in_single_dnf_layer tests.verify_002_wl_clipboard.Spec002ContractTests.test_inv2_wayland_only_no_x11_or_host_shims`
- [x] **Task 2:** Add `wl-paste --version` and `wl-copy --version` assertions to the unconditional `Smoke test image` block in `.github/workflows/build.yml`.
  - **Verify:** `python3 tests/verify_002_wl_clipboard.py && python3 tests/verify_001_ci_images_and_renovate.py`
