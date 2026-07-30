from __future__ import annotations

"""Update awareness using local package managers (never installs)."""

import shutil
from dataclasses import dataclass

from utils import run_command


@dataclass
class UpdateNotice:
    ecosystem: str
    name: str
    current: str | None
    latest: str | None
    detail: str


def collect_update_notices() -> list[UpdateNotice]:
    notices: list[UpdateNotice] = []
    notices.extend(_brew_outdated())
    notices.extend(_python_runtime())
    notices.extend(_node_runtime())
    notices.extend(_docker_runtime())
    notices.extend(_lm_studio_presence())
    return notices


def _brew_outdated() -> list[UpdateNotice]:
    if not shutil.which("brew"):
        return []
    rc, out, err = run_command(["brew", "outdated", "--verbose"], timeout=60)
    if rc != 0:
        return [
            UpdateNotice("Homebrew", "brew outdated", None, None, err or out or "Unable to query outdated packages.")
        ]
    notices = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        # name (1.0) < 2.0
        notices.append(UpdateNotice("Homebrew", line.split()[0], None, None, line))
    return notices


def _python_runtime() -> list[UpdateNotice]:
    py = shutil.which("python3")
    if not py:
        return []
    rc, out, _ = run_command([py, "--version"], timeout=10)
    return [UpdateNotice("Python", "python3", out if rc == 0 else None, None, f"Local interpreter: {py}")]


def _node_runtime() -> list[UpdateNotice]:
    node = shutil.which("node")
    if not node:
        return []
    rc, out, _ = run_command([node, "--version"], timeout=10)
    npm = shutil.which("npm")
    detail = f"node at {node}"
    if npm:
        nrc, nout, _ = run_command([npm, "outdated", "-g", "--depth=0"], timeout=45)
        if nrc in (0, 1) and nout.strip():
            detail += f"; npm outdated:\n{nout}"
    return [UpdateNotice("Node", "node", out if rc == 0 else None, None, detail)]


def _docker_runtime() -> list[UpdateNotice]:
    docker = shutil.which("docker")
    if not docker:
        return []
    rc, out, err = run_command([docker, "version", "--format", "{{.Server.Version}}"], timeout=15)
    return [
        UpdateNotice(
            "Docker",
            "docker",
            out if rc == 0 else None,
            None,
            out if rc == 0 else (err or "Docker daemon not reachable"),
        )
    ]


def _lm_studio_presence() -> list[UpdateNotice]:
    from pathlib import Path

    app = Path("/Applications/LM Studio.app")
    if not app.exists():
        return []
    return [
        UpdateNotice(
            "LM Studio",
            "LM Studio",
            None,
            None,
            "LM Studio is installed. Check the app’s own update UI for newer builds (no automatic install).",
        )
    ]
