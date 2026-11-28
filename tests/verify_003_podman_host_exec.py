#!/usr/bin/env python3
"""Contract tests for Spec 003: Host Podman Forwarding (devbox).

Uses Python 3 standard library only (zero external dependencies).
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


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


class Spec003ContractTests(unittest.TestCase):
    # Checks INV-1: devbox/podman.sh starts with #!/bin/sh, passes sh -n,
    # and delegates all arguments via exec distrobox-host-exec podman "$@".
    def test_inv1_podman_host_exec_shim_valid(self) -> None:
        shim_path = REPO_ROOT / "devbox" / "podman.sh"
        self.assertTrue(shim_path.is_file(), "devbox/podman.sh must exist")

        raw = shim_path.read_text(encoding="utf-8")
        self.assertNotIn("\r", raw, "devbox/podman.sh must use LF line endings (no CR)")
        self.assertTrue(
            raw.startswith("#!/bin/sh\n"),
            "devbox/podman.sh must start immediately with '#!/bin/sh\\n'",
        )

        body_lines = [line.strip() for line in raw.splitlines()[1:] if line.strip()]
        self.assertEqual(
            body_lines,
            ['exec distrobox-host-exec podman "$@"'],
            'devbox/podman.sh must delegate to exec distrobox-host-exec podman "$@"',
        )

        res = subprocess.run(
            ["sh", "-n", str(shim_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            res.returncode,
            0,
            f"sh -n failed for devbox/podman.sh: {res.stderr}",
        )

    # Checks INV-2: devbox/Containerfile copies podman.sh to /usr/local/bin/podman
    # and runs chmod +x /usr/local/bin/podman (preserving docker forwarding), while
    # obsidian/ remains untouched.
    def test_inv2_podman_baked_executable_in_devbox_only(self) -> None:
        devbox_cf = REPO_ROOT / "devbox" / "Containerfile"
        instructions = extract_containerfile_instructions(
            devbox_cf.read_text(encoding="utf-8")
        )

        copy_podman_re = re.compile(r"^COPY\s+podman\.sh\s+/usr/local/bin/podman$")
        chmod_podman_re = re.compile(r"^RUN\s+chmod\s+\+x\s+/usr/local/bin/podman$")
        copy_docker_re = re.compile(r"^COPY\s+docker\.sh\s+/usr/local/bin/docker$")
        chmod_docker_re = re.compile(r"^RUN\s+chmod\s+\+x\s+/usr/local/bin/docker$")

        copy_idx = next(
            (i for i, inst in enumerate(instructions) if copy_podman_re.match(inst)),
            None,
        )
        chmod_idx = next(
            (i for i, inst in enumerate(instructions) if chmod_podman_re.match(inst)),
            None,
        )
        self.assertIsNotNone(
            copy_idx,
            "devbox/Containerfile must COPY podman.sh to /usr/local/bin/podman",
        )
        self.assertIsNotNone(
            chmod_idx,
            "devbox/Containerfile must RUN chmod +x /usr/local/bin/podman",
        )
        self.assertLess(
            copy_idx,
            chmod_idx,
            "COPY podman.sh must precede chmod +x /usr/local/bin/podman",
        )

        self.assertTrue(
            any(copy_docker_re.match(inst) for inst in instructions),
            "devbox/Containerfile must preserve COPY docker.sh /usr/local/bin/docker",
        )
        self.assertTrue(
            any(chmod_docker_re.match(inst) for inst in instructions),
            "devbox/Containerfile must preserve RUN chmod +x /usr/local/bin/docker",
        )

        obsidian_shim = REPO_ROOT / "obsidian" / "podman.sh"
        self.assertFalse(
            obsidian_shim.exists(),
            "obsidian/podman.sh must not exist (devbox-only change)",
        )
        obsidian_cf_text = (REPO_ROOT / "obsidian" / "Containerfile").read_text(
            encoding="utf-8"
        )
        self.assertNotRegex(
            obsidian_cf_text,
            r"(?:podman\.sh|/usr/local/bin/podman)",
            "obsidian/Containerfile must not bake podman forwarding",
        )

    # Checks INV-3: .github/workflows/build.yml checks test -x /usr/local/bin/podman
    # inside the devbox-gated Smoke test image block strictly before GHCR login and push.
    def test_inv3_ci_smoke_test_checks_podman_for_devbox_before_push(self) -> None:
        workflow_path = REPO_ROOT / ".github" / "workflows" / "build.yml"
        text = workflow_path.read_text(encoding="utf-8")

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
        container_script_match = re.search(
            r'docker run --rm "ghcr\.io/hone/\$\{\{\s*matrix\.env\s*\}\}:latest" bash -ec \'(?P<script>.*?)\'',
            smoke_step,
            re.DOTALL,
        )
        self.assertIsNotNone(
            container_script_match,
            "Smoke test image step must run an in-container bash -ec script",
        )
        script = container_script_match.group("script")

        devbox_block_match = re.search(
            r'if\s+\[\s*"\$\{\{\s*matrix\.env\s*\}\}"\s*=\s*"devbox"\s*\];\s*then(?P<body>.*?)^\s*fi\b',
            script,
            re.DOTALL | re.MULTILINE,
        )
        self.assertIsNotNone(
            devbox_block_match,
            "Smoke test script must contain a devbox-gated if block",
        )
        devbox_body = devbox_block_match.group("body")
        self.assertRegex(
            devbox_body,
            r"(?m)^\s*test\s+-x\s+/usr/local/bin/podman\s*$",
            "devbox smoke test block must check 'test -x /usr/local/bin/podman'",
        )
        self.assertRegex(
            devbox_body,
            r"(?m)^\s*test\s+-x\s+/usr/local/bin/docker\s*$",
            "devbox smoke test block must preserve 'test -x /usr/local/bin/docker'",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
