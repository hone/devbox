#!/usr/bin/env python3
"""Contract tests for Spec 001: CI-Built Container Images & Renovate Automation.

Uses Python 3 standard library only (zero external dependencies).
"""

from __future__ import annotations

import configparser
import json
import re
import subprocess
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENVS = ("devbox", "obsidian")


def parse_justfile_recipes(text: str) -> dict[str, tuple[str, str]]:
    """Return mapping of recipe_name -> (header_line, body_text)."""
    recipes: dict[str, tuple[str, str]] = {}
    current_name: str | None = None
    current_header = ""
    body_lines: list[str] = []

    recipe_re = re.compile(r"^([a-zA-Z0-9_-]+)(?:\s+[^:]*)?:(.*)$")

    for line in text.splitlines():
        if line and not line[0].isspace() and not line.startswith("#"):
            if current_name is not None:
                recipes[current_name] = (current_header, "\n".join(body_lines))
                current_name = None
                body_lines = []

            if ":=" in line:
                continue

            match = recipe_re.match(line)
            if match:
                current_name = match.group(1)
                current_header = line
        elif current_name is not None:
            body_lines.append(line)

    if current_name is not None:
        recipes[current_name] = (current_header, "\n".join(body_lines))

    return recipes


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
            # Blank line breaks a logical block if malformed.
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


class Spec001ContractTests(unittest.TestCase):
    # Checks INV-1: Every tool in devbox/mise.global.toml and obsidian/mise.global.toml
    # specifies a concrete non-empty version string; "latest" is forbidden.
    def test_inv1_no_floating_latest_tool_versions(self) -> None:
        for env in ENVS:
            path = REPO_ROOT / env / "mise.global.toml"
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            tools = data.get("tools")
            self.assertIsInstance(tools, dict, f"{path}: missing [tools] table")
            self.assertTrue(tools, f"{path}: [tools] must not be empty")

            for tool_name, spec in tools.items():
                if isinstance(spec, str):
                    version = spec
                elif isinstance(spec, dict):
                    self.assertIn("version", spec, f"{path}: {tool_name} missing version")
                    version = spec["version"]
                else:
                    self.fail(f"{path}: unexpected tool spec type for {tool_name}: {type(spec)}")

                self.assertIsInstance(version, str, f"{path}: {tool_name} version must be string")
                cleaned = version.strip()
                self.assertTrue(cleaned, f"{path}: {tool_name} version must be non-empty")
                self.assertNotEqual(
                    cleaned.lower(),
                    "latest",
                    f"{path}: {tool_name} must not use floating 'latest'",
                )

    # Checks INV-2: Neither mise.global.toml uses explicit aqua: prefixes; settings are
    # preserved, and npm:defuddle in obsidian retains depends = ["node"].
    def test_inv2_renovate_compatible_mise_keys(self) -> None:
        for env in ENVS:
            path = REPO_ROOT / env / "mise.global.toml"
            data = tomllib.loads(path.read_text(encoding="utf-8"))

            settings = data.get("settings", {})
            self.assertIs(settings.get("color"), True, f"{path}: color setting must remain true")
            self.assertIs(
                settings.get("experimental"),
                True,
                f"{path}: experimental setting must remain true",
            )

            tools = data.get("tools", {})
            self.assertTrue(tools, f"{path}: [tools] must not be empty")
            for key in tools:
                self.assertFalse(
                    key.startswith("aqua:"),
                    f"{path}: tool '{key}' must not use explicit aqua: prefix",
                )

        obsidian_tools = tomllib.loads(
            (REPO_ROOT / "obsidian" / "mise.global.toml").read_text(encoding="utf-8")
        )["tools"]
        if "npm:defuddle" in obsidian_tools:
            defuddle = obsidian_tools["npm:defuddle"]
            self.assertIsInstance(defuddle, dict, "obsidian npm:defuddle must be an inline table")
            self.assertEqual(
                defuddle.get("depends"),
                ["node"],
                "obsidian npm:defuddle must preserve depends = ['node']",
            )

    # Checks INV-3: Both Containerfiles start with FROM ghcr.io/ublue-os/fedora-toolbox:latest@sha256:<64-hex>
    # and declare LABEL org.opencontainers.image.source="https://github.com/hone/devbox".
    def test_inv3_base_image_pinned_and_oci_source_label(self) -> None:
        from_re = re.compile(
            r"^FROM\s+ghcr\.io/ublue-os/fedora-toolbox:latest@sha256:([0-9a-f]{64})$"
        )
        label_re = re.compile(
            r'^LABEL\s+org\.opencontainers\.image\.source="?https://github\.com/hone/devbox"?$',
            re.MULTILINE,
        )

        for env in ENVS:
            path = REPO_ROOT / env / "Containerfile"
            text = path.read_text(encoding="utf-8")
            instructions = extract_containerfile_instructions(text)
            self.assertTrue(instructions, f"{path}: Containerfile is empty")
            self.assertRegex(
                instructions[0],
                from_re,
                f"{path}: first instruction must pin fedora-toolbox to latest@sha256:<digest>",
            )
            self.assertRegex(
                text,
                label_re,
                f"{path}: must declare org.opencontainers.image.source label",
            )

    # Checks INV-4: Both Containerfiles run mise install in a single RUN instruction with an
    # optional non-empty github_token secret mount and never leak GITHUB_TOKEN via ARG or ENV.
    def test_inv4_optional_non_leaking_buildkit_secret(self) -> None:
        mount_run_re = re.compile(
            r"^RUN\s+--mount=type=secret,id=github_token,required=false\b"
            r".*\[\s*-s\s+/run/secrets/github_token\s*\]"
            r".*\bGITHUB_TOKEN\b"
            r".*\bmise\s+install\b"
        )
        leak_re = re.compile(r"^\s*(?:ARG|ENV)\s+.*\bGITHUB_TOKEN\b", re.MULTILINE)

        for env in ENVS:
            path = REPO_ROOT / env / "Containerfile"
            text = path.read_text(encoding="utf-8")
            instructions = extract_containerfile_instructions(text)
            self.assertTrue(
                any(mount_run_re.search(inst) for inst in instructions),
                f"{path}: single RUN instruction must mount optional github_token secret (-s) for mise install",
            )
            self.assertNotRegex(
                text,
                leak_re,
                f"{path}: must never expose GITHUB_TOKEN via ARG or ENV",
            )

    # Checks INV-5: renovate.json is valid JSON extending config:recommended, docker:pinDigests,
    # and helpers:pinGitHubActionDigests, enables PR platform automerge, schedules fedora-toolbox
    # weekly, and keeps mise tools ungrouped (including no catch-all groupName rule).
    def test_inv5_renovate_config_contract(self) -> None:
        path = REPO_ROOT / "renovate.json"
        self.assertTrue(path.is_file(), "renovate.json must exist")
        cfg = json.loads(path.read_text(encoding="utf-8"))

        extends = cfg.get("extends", [])
        self.assertIn("config:recommended", extends)
        self.assertIn("docker:pinDigests", extends)
        self.assertIn("helpers:pinGitHubActionDigests", extends)
        self.assertIs(cfg.get("platformAutomerge"), True)
        self.assertIs(cfg.get("automerge"), True)
        self.assertEqual(cfg.get("automergeType"), "pr")

        rules = cfg.get("packageRules", [])
        self.assertIsInstance(rules, list)

        weekly_tokens = (
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            "weekly",
        )
        found_base_schedule = False
        for rule in rules:
            managers = rule.get("matchManagers")
            packages = rule.get("matchPackageNames", [])
            if managers is None or "mise" in managers:
                self.assertNotIn(
                    "groupName",
                    rule,
                    "renovate.json must not group mise tools (directly or via catch-all rule)",
                )
            if (
                isinstance(managers, list)
                and "dockerfile" in managers
                and "ghcr.io/ublue-os/fedora-toolbox" in packages
            ):
                schedule = rule.get("schedule", [])
                self.assertTrue(
                    isinstance(schedule, list) and len(schedule) > 0,
                    "fedora-toolbox rule must specify a non-empty schedule list",
                )
                joined = " ".join(schedule).lower()
                self.assertTrue(
                    any(tok in joined for tok in weekly_tokens),
                    f"fedora-toolbox schedule must be weekly, got: {schedule}",
                )
                found_base_schedule = True

        self.assertTrue(
            found_base_schedule,
            "renovate.json must include a weekly schedule packageRule for fedora-toolbox",
        )

    # Checks INV-6: .github/workflows/build.yml builds devbox and obsidian for linux/amd64,
    # serializes main publishes via concurrency, smoke-tests configured tools & paths before pushing,
    # and gates GHCR push strictly to main push or main workflow_dispatch.
    def test_inv6_ci_workflow_contract(self) -> None:
        path = REPO_ROOT / ".github" / "workflows" / "build.yml"
        self.assertTrue(path.is_file(), ".github/workflows/build.yml must exist")
        text = path.read_text(encoding="utf-8")

        # Triggers (both pull_request and push must target main)
        self.assertRegex(
            text,
            r"(?ms)^\s+pull_request:\n\s+branches:\s*\[\s*['\"]?main['\"]?\s*\]",
        )
        self.assertRegex(
            text,
            r"(?ms)^\s+push:\n\s+branches:\s*\[\s*['\"]?main['\"]?\s*\]",
        )
        self.assertRegex(text, r"(?m)^\s+workflow_dispatch:")

        # Concurrency guard prevents parallel main pushes racing on :latest
        self.assertRegex(text, r"(?m)^concurrency:")
        self.assertIn("cancel-in-progress:", text)

        # Permissions
        self.assertRegex(text, r"(?m)^\s+contents:\s+read\b")
        self.assertRegex(text, r"(?m)^\s+packages:\s+write\b")

        # Matrix covers both environments
        self.assertRegex(text, r"matrix:")
        self.assertIn("devbox", text)
        self.assertIn("obsidian", text)

        # Build step uses Buildx + build-push-action with load: true, push: false, linux/amd64,
        # GHA cache, OCI labels, and BuildKit secret
        self.assertIn("docker/setup-buildx-action", text)
        self.assertIn("docker/build-push-action", text)
        self.assertRegex(text, r"(?m)^\s+platforms:\s+linux/amd64\b")
        self.assertRegex(text, r"(?m)^\s+load:\s+true\b")
        self.assertRegex(text, r"(?m)^\s+push:\s+false\b")
        self.assertIn("org.opencontainers.image.source=", text)
        self.assertIn("org.opencontainers.image.revision=", text)
        self.assertIn("type=gha", text)
        self.assertRegex(text, r"github_token=\$\{\{\s*secrets\.GITHUB_TOKEN\s*\}\}")

        # Smoke test assertions and ordering (must precede GHCR login and docker push)
        smoke_idx = text.find("mise ls --missing")
        self.assertNotEqual(smoke_idx, -1, "workflow must smoke-test via 'mise ls --missing'")
        self.assertIn("mise ls --current --json", text)
        self.assertIn("/etc/mise/config.toml", text)
        self.assertIn("/etc/mise/setup.sh", text)
        self.assertIn("os.path.exists", text)
        self.assertIn("/usr/local/bin/docker", text)
        self.assertIn("pg_ctl", text)
        self.assertIn("valkey-server", text)

        login_idx = text.find("docker/login-action")
        push_idx = text.find("docker push")
        self.assertNotEqual(login_idx, -1, "workflow must log in via docker/login-action")
        self.assertNotEqual(push_idx, -1, "workflow must push tested image via docker push")
        self.assertLess(smoke_idx, login_idx, "smoke test must run before GHCR login")
        self.assertLess(login_idx, push_idx, "GHCR login must run before docker push")

        # GHCR target and strict main-only push gate (for both push and workflow_dispatch)
        self.assertIn("registry: ghcr.io", text)
        self.assertIn("ghcr.io/hone/", text)
        self.assertIn(":latest", text)
        self.assertIn(":sha-", text)
        gate_re = re.compile(
            r"if:\s+\(github\.event_name\s*==\s*'push'\s*&&\s*github\.ref\s*==\s*'refs/heads/main'\)"
            r"\s*\|\|\s*"
            r"\(github\.event_name\s*==\s*'workflow_dispatch'\s*&&\s*github\.ref\s*==\s*'refs/heads/main'\)"
        )
        self.assertGreaterEqual(
            len(gate_re.findall(text)),
            2,
            "both GHCR login and docker push steps must be gated strictly to main",
        )

    # Checks INV-7: devbox/distrobox.ini and obsidian/distrobox.ini point to
    # ghcr.io/hone/<env>:latest with pull=true and preserve replace and init_hooks.
    def test_inv7_pull_first_distrobox_manifests(self) -> None:
        for env in ENVS:
            path = REPO_ROOT / env / "distrobox.ini"
            parser = configparser.ConfigParser()
            parser.read(path, encoding="utf-8")
            self.assertIn(env, parser, f"{path}: missing [{env}] section")
            section = parser[env]
            self.assertEqual(section.get("image"), f"ghcr.io/hone/{env}:latest")
            self.assertEqual(section.get("pull"), "true")
            self.assertEqual(section.get("replace"), "true")
            self.assertEqual(section.get("init_hooks", "").strip('"'), "/etc/mise/setup.sh")

    # Checks INV-8: Justfile defines pull, decouples create/rebuild from build,
    # and provides non-mutating mktemp+trap local escape hatches via _assemble-local.
    def test_inv8_pull_first_justfile_and_local_escape_hatches(self) -> None:
        justfile = (REPO_ROOT / "Justfile").read_text(encoding="utf-8")
        recipes = parse_justfile_recipes(justfile)

        # pull recipe
        self.assertIn("pull", recipes, "Justfile must define 'pull' recipe")
        self.assertIn("podman pull ghcr.io/hone/{{env}}:latest", recipes["pull"][1])

        # Default create & rebuild must NOT depend on local build
        for name in ("create", "rebuild"):
            self.assertIn(name, recipes, f"Justfile must define '{name}' recipe")
            header, body = recipes[name]
            self.assertNotIn(
                "(build",
                header,
                f"Justfile '{name}' must not depend on local build recipe",
            )
            self.assertIn("distrobox assemble create", body)
            self.assertIn("{{env}}/distrobox.ini", body)
        self.assertIn("--replace", recipes["rebuild"][1])

        # Local escape hatches
        for name in ("build", "update"):
            self.assertIn(name, recipes, f"Justfile must retain '{name}' recipe")
            self.assertIn("podman build", recipes[name][1])

        self.assertIn("_assemble-local", recipes, "Justfile must define '_assemble-local' helper")
        _, helper_body = recipes["_assemble-local"]
        self.assertIn("mktemp", helper_body)
        self.assertIn("trap", helper_body)
        self.assertIn("localhost/{{env}}-base:latest", helper_body)
        self.assertIn("pull=false", helper_body)
        self.assertIn("distrobox assemble create", helper_body)
        self.assertNotRegex(
            helper_body,
            r"\bsed\s+-i\b",
            "_assemble-local must never edit distrobox.ini in place",
        )

        for name in ("create-local", "rebuild-local"):
            self.assertIn(name, recipes, f"Justfile must define '{name}' escape hatch")
            header, _ = recipes[name]
            self.assertIn("(build env)", header, f"'{name}' must depend on (build env)")
            self.assertIn("_assemble-local", header, f"'{name}' must delegate to _assemble-local")
        self.assertIn("--replace", recipes["rebuild-local"][0])

        # Existing recipes preserved
        for name in ("enter", "rm", "pg-start", "pg-stop", "pg-status"):
            self.assertIn(name, recipes, f"Justfile must preserve existing '{name}' recipe")

    # Checks INV-9: Existing shell scripts pass bash -n / sh -n syntax checks.
    def test_inv9_shell_scripts_syntax_valid(self) -> None:
        checks = [
            (["bash", "-n", str(REPO_ROOT / "devbox" / "setup.sh")]),
            (["bash", "-n", str(REPO_ROOT / "obsidian" / "setup.sh")]),
            (["sh", "-n", str(REPO_ROOT / "devbox" / "docker.sh")]),
        ]
        for cmd in checks:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(
                res.returncode,
                0,
                f"Syntax check failed for {' '.join(cmd)}: {res.stderr}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
