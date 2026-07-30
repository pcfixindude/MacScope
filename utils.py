from __future__ import annotations

import json
import logging
import plistlib
import re
from pathlib import Path
from typing import Any, Sequence

from config import LOG_PATH, ensure_data_dirs

ensure_data_dirs()
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
# Also log to stderr for launcher diagnostics
_console = logging.StreamHandler()
_console.setLevel(logging.WARNING)
logging.getLogger("macscope").addHandler(_console)
logger = logging.getLogger("macscope")


def run_command(
    args: Sequence[str],
    timeout: int = 20,
    *,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """Run a subprocess with an argument list (never shell=True)."""
    import subprocess

    try:
        completed = subprocess.run(
            list(args),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
        return completed.returncode, completed.stdout.strip(), completed.stderr.strip()
    except Exception as exc:
        logger.exception("Command failed: %s", args)
        return 1, "", str(exc)


def json_dumps(data: object) -> str:
    return json.dumps(data, default=str, ensure_ascii=False)


def json_loads(raw: str | None, default: Any = None) -> Any:
    if not raw:
        return {} if default is None else default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {} if default is None else default


def read_plist(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            data = plistlib.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("Failed to parse plist %s: %s", path, exc)
        return {}


def codesign_team_info(path: str | Path) -> dict[str, str]:
    target = str(path)
    info: dict[str, str] = {}
    if not target:
        return info
    _, out, err = run_command(["codesign", "--display", "--verbose=4", target], timeout=15)
    text = "\n".join(x for x in (out, err) if x)
    for pattern, key in (
        (r"Authority=(.+)", "authority"),
        (r"TeamIdentifier=(.+)", "team_id"),
        (r"Identifier=(.+)", "identifier"),
    ):
        match = re.search(pattern, text)
        if match:
            info[key] = match.group(1).strip()
    return info


def codesign_identity(path: str | Path) -> str | None:
    return codesign_team_info(path).get("authority")


def parse_program_from_plist(data: dict[str, Any]) -> str | None:
    program = data.get("Program")
    if isinstance(program, str) and program.strip():
        return program.strip()
    args = data.get("ProgramArguments")
    if isinstance(args, list) and args:
        first = args[0]
        if isinstance(first, str) and first.strip():
            return first.strip()
    return None


def path_exists(path: str | None) -> bool:
    if not path:
        return False
    try:
        return Path(path).expanduser().exists()
    except OSError:
        return False


def resolve_path(path: str | Path | None) -> Path | None:
    if path is None:
        return None
    try:
        return Path(path).expanduser().resolve()
    except OSError:
        return None


def unique_trash_destination(trash_dir: Path, name: str) -> Path:
    candidate = trash_dir / name
    if not candidate.exists():
        return candidate
    stem = Path(name).stem
    suffix = Path(name).suffix
    index = 1
    while True:
        candidate = trash_dir / f"{stem} {index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def dir_size_bytes(path: Path, *, max_files: int = 5000) -> int:
    """Bounded directory size calculation."""
    total = 0
    count = 0
    try:
        for child in path.rglob("*"):
            if count >= max_files:
                break
            count += 1
            try:
                if child.is_file() and not child.is_symlink():
                    total += child.stat().st_size
            except OSError:
                continue
    except OSError:
        return total
    return total


def format_bytes(num: float | int | None) -> str:
    if num is None:
        return "—"
    value = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"
