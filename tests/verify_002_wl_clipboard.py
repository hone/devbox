#!/usr/bin/env python3
"""Contract tests for Spec 002: Wayland Clipboard Support (wl-clipboard).

Uses Python 3 standard library only (zero external dependencies).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENVS = ("devbox", "obsidian")


def extract_containerfile_instructions(text: str) -> list[str]:
    """Return logical Containerfile instructions with line continuations joined."""
    instructions: list[str] = []
    buf: list[str] = []

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not buf:
            if not stripped or stripped.startswith("#"):
                continue
        elif not stripped:
            buf.append("")
            continue
        elif stripped.startswith("#"):
            continue

        if stripped.endswith("\\"):
            buf.append(stripped[:-1].rstrip())
        else:
            buf.append(stripped)
            instructions.append(" ".join(buf))
            buf = []

    if buf:
        instructions.append(" ".join(buf))

    return instructions


class Spec002ContractTests(unittest.TestCase):
    # Checks INV-1: Both devbox/Containerfile and obsidian/Containerfile include wl-clipboard
    # as a discrete package token inside their single dnf install -y instruction (before dnf clean all).
    def test_inv1_wl_clipboard_baked_in_single_dnf_layer(self) -> None:
        for env in ENVS:
            path = REPO_ROOT / env / "Containerfile"
            instructions = extract_containerfile_instructions(
                path.read_text(encoding="utf-8")
            )
            dnf_runs = [
                inst
                for inst in instructions
                if inst.startswith("RUN ") and re.search(r"\bdnf\s+install\b", inst)
            ]
            self.assertEqual(
                len(dnf_runs),
                1,
                f"{path}: expected exactly 1 RUN instruction with 'dnf install', found {len(dnf_runs)}",
            )

            match = re.search(
                r"\bdnf\s+install\s+-y\b(?P<pkgs>[^&;]+)&&\s*dnf\s+clean\s+all\b",
                dnf_runs[0],
            )
            self.assertIsNotNone(
                match,
                f"{path}: single dnf install -y instruction must immediately chain into 'dnf clean all'",
            )
            pkgs = match.group("pkgs")
            self.assertRegex(
                pkgs,
                r"(?<!\S)wl-clipboard(?!\S)",
                f"{path}: single dnf install -y layer must include discrete package 'wl-clipboard'",
            )

    # Checks INV-2: Neither Containerfile installs xclip or xsel, and neither env adds
    # wl-copy or wl-paste distrobox-host-exec wrapper scripts.
    def test_inv2_wayland_only_no_x11_or_host_shims(self) -> None:
        for env in ENVS:
            env_dir = REPO_ROOT / env
            containerfile_text = (env_dir / "Containerfile").read_text(encoding="utf-8")
            self.assertNotRegex(
                containerfile_text,
                r"(?<!\S)(?:xclip|xsel)(?!\S)",
                f"{env}/Containerfile must not install X11 clipboard tools (xclip/xsel)",
            )

            for file_path in sorted(env_dir.rglob("*")):
                if not file_path.is_file():
                    continue
                self.assertNotRegex(
                    file_path.name,
                    r"^wl-(?:copy|paste)(?:\..+)?$",
                    f"{file_path.relative_to(REPO_ROOT)} host-exec shim must not exist",
                )
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                self.assertNotRegex(
                    content,
                    r"distrobox-host-exec\b[^\n]*\b(?:wl-copy|wl-paste)\b",
                    f"{file_path.relative_to(REPO_ROOT)} must not wrap wl-copy/wl-paste with distrobox-host-exec",
                )

    # Checks INV-3: .github/workflows/build.yml runs wl-paste --version and wl-copy --version
    # unconditionally inside the Smoke test image container script for both matrix environments
    # strictly before GHCR login and docker push.
    def test_inv3_ci_smoke_test_checks_wl_clipboard_both_envs_before_push(self) -> None:
        workflow_path = REPO_ROOT / ".github" / "workflows" / "build.yml"
        text = workflow_path.read_text(encoding="utf-8")

        matrix_match = re.search(
            r"^\s*matrix:\s*\n(?:\s+.*\n)*?\s*env:\s*\[(?P<envs>[^\]]+)\]",
            text,
            re.MULTILINE,
        )
        self.assertIsNotNone(matrix_match, "workflow must define a matrix.env list")
        matrix_envs = {
            item.strip().strip("'\"") for item in matrix_match.group("envs").split(",")
        }
        self.assertTrue(
            {"devbox", "obsidian"}.issubset(matrix_envs),
            f"workflow matrix.env must include both devbox and obsidian, got: {sorted(matrix_envs)}",
        )

        smoke_idx = text.find("- name: Smoke test image")
        login_idx = text.find("docker/login-action")
        push_idx = text.find("docker push")
        self.assertNotEqual(smoke_idx, -1, "workflow must define 'Smoke test image' step")
        self.assertNotEqual(login_idx, -1, "workflow must define docker/login-action")
        self.assertNotEqual(push_idx, -1, "workflow must define docker push")
        self.assertLess(smoke_idx, login_idx, "Smoke test image must precede GHCR login")
        self.assertLess(login_idx, push_idx, "GHCR login must precede docker push")

        next_step = re.search(r"^\s*-\s+name:", text[smoke_idx + 1 :], re.MULTILINE)
        smoke_step = (
            text[smoke_idx : smoke_idx + 1 + next_step.start()]
            if next_step
            else text[smoke_idx:login_idx]
        )
        self.assertNotRegex(
            smoke_step,
            r"^\s+if:",
            "Smoke test image step must not be conditionally gated via step-level 'if:'",
        )

        container_script_match = re.search(
            r'docker run --rm "ghcr\.io/hone/\$\{\{\s*matrix\.env\s*\}\}:latest" bash -ec \'(?P<script>.*?)\'',
            smoke_step,
            re.DOTALL,
        )
        self.assertIsNotNone(
            container_script_match,
            "Smoke test image step must run an in-container bash -ec script against ghcr.io/hone/${{ matrix.env }}:latest",
        )
        script = container_script_match.group("script")
        unconditional_script = re.sub(
            r"(?ms)^\s*if\b.*?^\s*fi\b",
            "",
            script,
        )

        for cmd in ("wl-paste --version", "wl-copy --version"):
            pattern = re.compile(rf"^\s*{re.escape(cmd)}\b", re.MULTILINE)
            self.assertRegex(
                unconditional_script,
                pattern,
                f"Smoke test container script must run '{cmd}' unconditionally (outside any if..fi block)",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
