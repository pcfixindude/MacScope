from __future__ import annotations

import getpass
import json
import os
import shutil
import signal
from pathlib import Path
from typing import Sequence

from config import APP_NAME, BACKUPS_DIR, BASE_DIR
from database import SessionLocal
from macscope.backup import create_file_backup, move_to_disabled_items, restore_file_backup
from macscope.redaction import redact_command
from macscope.settings import load_settings
from models import Event
from protection import (
    is_protected_path,
    is_protected_process,
    validate_app_bundle_target,
    validate_launch_plist_target,
)
from utils import logger, run_command, unique_trash_destination

# Re-exported for tests and callers that monkeypatch backup location.
__all__ = [
    "ActionError",
    "BACKUPS_DIR",
    "backup_plist",
    "brew_autostart_disable",
    "brew_autostart_enable",
    "brew_cleanup_preview",
    "brew_cmd",
    "brew_dependency_review",
    "brew_upgrade",
    "delete_venv",
    "disable_launch_agent",
    "docker_prune_preview",
    "docker_prune_selected",
    "docker_remove_container",
    "docker_remove_image",
    "docker_restart",
    "docker_start",
    "docker_stop",
    "enable_launch_agent",
    "force_quit_application",
    "force_quit_process",
    "load_launch_item",
    "move_app_to_trash",
    "open_application",
    "quit_application",
    "remove_conda_env",
    "remove_node_modules",
    "remove_pyenv_version",
    "restart_brew_service",
    "restart_launch_item",
    "restore_plist_backup",
    "reveal_in_finder",
    "start_brew_service",
    "stop_brew_service",
    "stop_process",
    "system_launch_item_instructions",
    "trash_path",
    "unload_launch_item",
    "uninstall_brew",
    "uninstall_npm_global",
]


class ActionError(RuntimeError):
    """Raised when a guarded management action cannot proceed."""


_VENV_DIR_NAMES = frozenset({".venv", "venv", "env", ".env"})
_DOCKER_PRUNE_CATEGORIES = frozenset(
    {"containers", "images", "volumes", "networks", "build-cache"}
)


def _current_user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def _require_destructive() -> None:
    settings = load_settings()
    if not settings.destructive_allowed():
        raise ActionError(
            "Destructive actions are disabled. Enable them in Settings and acknowledge the safety notice."
        )


def _resolve_path(path: str | Path) -> Path:
    try:
        return Path(path).expanduser().resolve()
    except OSError as exc:
        raise ActionError(f"Cannot resolve path: {exc}") from exc


def _command_display(args: Sequence[str]) -> str:
    return redact_command(" ".join(args))


def _record(
    action: str,
    target: object,
    result: str,
    message: str = "",
    *,
    target_type: str | None = None,
    target_path: str | Path | None = None,
    command: Sequence[str] | None = None,
    exit_code: int | None = None,
    stdout: str | None = None,
    stderr: str | None = None,
    backup_path: str | Path | None = None,
    restore_available: bool = False,
) -> None:
    with SessionLocal() as db:
        db.add(
            Event(
                action=action,
                target=str(target),
                result=result,
                message=message,
                user=_current_user(),
                target_type=target_type,
                target_path=str(target_path) if target_path is not None else None,
                command_display=_command_display(command) if command else None,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                backup_path=str(backup_path) if backup_path is not None else None,
                restore_available=restore_available,
            )
        )
        db.commit()
    logger.info(
        "action=%s target=%s result=%s user=%s message=%s",
        action,
        target,
        result,
        _current_user(),
        message,
    )


def _run_recorded(
    action: str,
    target: object,
    args: list[str],
    *,
    target_type: str | None = None,
    target_path: str | Path | None = None,
    timeout: int = 30,
    backup_path: str | Path | None = None,
    restore_available: bool = False,
    blocked_message: str | None = None,
) -> tuple[int, str, str]:
    if blocked_message:
        _record(
            action,
            target,
            "blocked",
            blocked_message,
            target_type=target_type,
            target_path=target_path,
            command=args,
        )
        raise ActionError(blocked_message)
    rc, out, err = run_command(args, timeout=timeout)
    message = out or err
    _record(
        action,
        target,
        "success" if rc == 0 else "failed",
        message,
        target_type=target_type,
        target_path=target_path,
        command=args,
        exit_code=rc,
        stdout=out,
        stderr=err,
        backup_path=backup_path,
        restore_available=restore_available,
    )
    if rc != 0:
        raise ActionError(message or f"{action} failed")
    return rc, out, err


def _launch_domain() -> str:
    return f"gui/{os.getuid()}"


def _path_under_roots(path: Path, roots: list[str | Path]) -> bool:
    resolved = path.resolve()
    for root in roots:
        try:
            root_path = Path(root).expanduser().resolve()
        except OSError:
            continue
        if resolved == root_path or root_path in resolved.parents:
            return True
    return False


def _looks_like_venv(path: Path) -> bool:
    if (path / "pyvenv.cfg").is_file():
        return True
    if (path / "bin" / "python").exists() and (path / "bin" / "activate").exists():
        return True
    return path.name in _VENV_DIR_NAMES and (path / "bin").is_dir()


def _is_macscope_venv(path: Path) -> bool:
    if "MacScope" in str(path):
        return True
    candidates = [
        BASE_DIR / ".venv",
        BASE_DIR / ".venv312",
        BASE_DIR.parent / "MacScope" / ".venv",
    ]
    try:
        resolved = path.resolve()
        for candidate in candidates:
            try:
                if resolved == candidate.resolve():
                    return True
            except OSError:
                continue
    except OSError:
        pass
    if path.name in _VENV_DIR_NAMES and (path.parent / "app.py").exists():
        try:
            if path.parent.resolve() == BASE_DIR.resolve():
                return True
        except OSError:
            pass
    return False


def _validate_venv_target(path: str | Path) -> Path:
    resolved = _resolve_path(path)
    if not resolved.exists() or not resolved.is_dir():
        raise ActionError("Virtual environment path does not exist.")
    if is_protected_path(str(resolved)):
        raise ActionError("Protected path.")
    if not _looks_like_venv(resolved):
        raise ActionError("Path does not look like a Python virtual environment.")
    if _is_macscope_venv(resolved):
        raise ActionError(f"{APP_NAME}'s own virtual environment cannot be removed.")
    return resolved


def _validate_node_modules_target(path: str | Path) -> Path:
    resolved = _resolve_path(path)
    if not resolved.exists() or not resolved.is_dir():
        raise ActionError("node_modules path does not exist.")
    if resolved.name != "node_modules":
        raise ActionError("Target is not a node_modules directory.")
    if is_protected_path(str(resolved)):
        raise ActionError("Protected path.")
    return resolved


def _validate_cleanup_path(path: str | Path, allowed_roots: list[str | Path]) -> Path:
    resolved = _resolve_path(path)
    if not resolved.exists():
        raise ActionError("Path does not exist.")
    if is_protected_path(str(resolved)):
        raise ActionError("Protected path.")
    if not allowed_roots:
        raise ActionError("No allowed roots configured for this cleanup action.")
    if not _path_under_roots(resolved, allowed_roots):
        raise ActionError("Path is outside the reviewed cleanup scope.")
    return resolved


def _trash_directory() -> Path:
    trash_dir = Path.home() / ".Trash"
    trash_dir.mkdir(parents=True, exist_ok=True)
    return trash_dir


def _move_to_trash(source: Path) -> Path:
    destination = unique_trash_destination(_trash_directory(), source.name)
    shutil.move(str(source), str(destination))
    return destination


def brew_cmd(*parts: str) -> list[str]:
    """Build a Homebrew command argument list."""
    brew = shutil.which("brew")
    if not brew:
        raise ActionError("Homebrew not found on PATH.")
    return [brew, *parts]


def docker_cmd(*parts: str) -> list[str]:
    """Build a Docker command argument list."""
    docker = shutil.which("docker")
    if not docker:
        raise ActionError("Docker not found on PATH.")
    return [docker, *parts]


def stop_process(pid: int, *, name: str | None = None, exe: str | None = None) -> None:
    """Send SIGTERM to a process after protection checks."""
    blocked, reason = is_protected_process(pid=pid, name=name, exe=exe)
    if blocked:
        _record(
            "stop_process",
            pid,
            "blocked",
            reason,
            target_type="process",
            target_path=exe,
        )
        raise ActionError(reason)
    try:
        os.kill(pid, signal.SIGTERM)
        _record(
            "stop_process",
            pid,
            "success",
            "Sent SIGTERM",
            target_type="process",
            target_path=exe,
        )
    except ProcessLookupError:
        _record("stop_process", pid, "failed", "Process not found", target_type="process")
        raise ActionError("Process not found.")
    except PermissionError:
        _record("stop_process", pid, "failed", "Permission denied", target_type="process")
        raise ActionError("Permission denied stopping process.")
    except Exception as exc:
        _record("stop_process", pid, "failed", str(exc), target_type="process")
        raise ActionError(str(exc)) from exc


def force_quit_process(pid: int, *, name: str | None = None, exe: str | None = None) -> None:
    """Send SIGKILL only after caller has already confirmed twice in the UI."""
    _require_destructive()
    blocked, reason = is_protected_process(pid=pid, name=name, exe=exe)
    if blocked:
        _record(
            "force_quit_process",
            pid,
            "blocked",
            reason,
            target_type="process",
            target_path=exe,
        )
        raise ActionError(reason)
    try:
        os.kill(pid, signal.SIGKILL)
        _record(
            "force_quit_process",
            pid,
            "success",
            "Sent SIGKILL",
            target_type="process",
            target_path=exe,
        )
    except ProcessLookupError:
        _record("force_quit_process", pid, "failed", "Process not found", target_type="process")
        raise ActionError("Process not found.")
    except PermissionError:
        _record("force_quit_process", pid, "failed", "Permission denied", target_type="process")
        raise ActionError("Permission denied force-quitting process.")
    except Exception as exc:
        _record("force_quit_process", pid, "failed", str(exc), target_type="process")
        raise ActionError(str(exc)) from exc


def backup_plist(path: str | Path) -> Path:
    """Copy a plist into the MacScope backups directory before mutation."""
    ok, reason, resolved = validate_launch_plist_target(path)
    target = resolved
    if target is None:
        try:
            target = Path(path).expanduser().resolve()
        except OSError as exc:
            raise ActionError(f"Cannot resolve plist: {exc}") from exc
    if not target.exists() or (
        target.suffix != ".plist" and not target.name.endswith(".plist.disabled")
    ):
        raise ActionError(reason or "Invalid plist path.")
    if is_protected_path(str(target)):
        raise ActionError("Cannot back up protected Apple/system plists.")
    if not ok:
        raise ActionError(reason or "Invalid plist path.")
    try:
        dest = create_file_backup(target, kind="plist")
    except (FileNotFoundError, PermissionError) as exc:
        _record("backup_plist", target, "failed", str(exc), target_type="plist", target_path=target)
        raise ActionError(str(exc)) from exc
    _record(
        "backup_plist",
        target,
        "success",
        str(dest),
        target_type="plist",
        target_path=target,
        backup_path=dest,
        restore_available=True,
    )
    return dest


def restore_plist_backup(backup_path: str | Path) -> Path:
    """Restore a plist from a MacScope backup record."""
    backup = _resolve_path(backup_path)
    try:
        restored = restore_file_backup(backup)
    except (FileNotFoundError, PermissionError) as exc:
        _record(
            "restore_plist_backup",
            backup,
            "failed",
            str(exc),
            target_type="plist",
            target_path=backup,
            backup_path=backup,
        )
        raise ActionError(str(exc)) from exc
    _record(
        "restore_plist_backup",
        restored,
        "success",
        f"Restored from {backup}",
        target_type="plist",
        target_path=restored,
        backup_path=backup,
        restore_available=True,
    )
    return restored


def unload_launch_item(path: str | Path) -> None:
    """Unload a user LaunchAgent for the current session (plist preserved)."""
    ok, reason, resolved = validate_launch_plist_target(path)
    if not ok or resolved is None:
        _record(
            "unload_launch_item",
            path,
            "blocked",
            reason,
            target_type="launch_agent",
            target_path=path,
        )
        raise ActionError(reason)
    args = ["launchctl", "bootout", _launch_domain(), str(resolved)]
    _run_recorded(
        "unload_launch_item",
        resolved,
        args,
        target_type="launch_agent",
        target_path=resolved,
        timeout=30,
    )


def load_launch_item(path: str | Path) -> None:
    """Bootstrap a user LaunchAgent plist into the current GUI domain."""
    ok, reason, resolved = validate_launch_plist_target(path)
    if not ok or resolved is None:
        _record(
            "load_launch_item",
            path,
            "blocked",
            reason,
            target_type="launch_agent",
            target_path=path,
        )
        raise ActionError(reason)
    args = ["launchctl", "bootstrap", _launch_domain(), str(resolved)]
    _run_recorded(
        "load_launch_item",
        resolved,
        args,
        target_type="launch_agent",
        target_path=resolved,
        timeout=30,
    )


def restart_launch_item(path: str | Path) -> None:
    """Unload and reload a user LaunchAgent."""
    ok, reason, resolved = validate_launch_plist_target(path)
    if not ok or resolved is None:
        _record(
            "restart_launch_item",
            path,
            "blocked",
            reason,
            target_type="launch_agent",
            target_path=path,
        )
        raise ActionError(reason)
    domain = _launch_domain()
    bootout = ["launchctl", "bootout", domain, str(resolved)]
    rc, out, err = run_command(bootout, timeout=30)
    if rc != 0 and "No such process" not in (out + err):
        _record(
            "restart_launch_item",
            resolved,
            "failed",
            out or err,
            target_type="launch_agent",
            target_path=resolved,
            command=bootout,
            exit_code=rc,
            stdout=out,
            stderr=err,
        )
        raise ActionError(out or err or "launchctl bootout failed")
    bootstrap = ["launchctl", "bootstrap", domain, str(resolved)]
    _run_recorded(
        "restart_launch_item",
        resolved,
        bootstrap,
        target_type="launch_agent",
        target_path=resolved,
        timeout=30,
    )


def disable_launch_agent(path: str | Path) -> Path:
    """Persistently disable a user LaunchAgent by unloading and renaming the plist."""
    _require_destructive()
    ok, reason, resolved = validate_launch_plist_target(path)
    if not ok or resolved is None:
        _record(
            "disable_launch_agent",
            path,
            "blocked",
            reason,
            target_type="launch_agent",
            target_path=path,
        )
        raise ActionError(reason)
    backup = backup_plist(resolved)
    try:
        unload_launch_item(str(resolved))
    except ActionError:
        pass
    disabled = resolved.with_suffix(resolved.suffix + ".disabled")
    if disabled.exists():
        _record(
            "disable_launch_agent",
            resolved,
            "failed",
            f"{disabled.name} already exists",
            target_type="launch_agent",
            target_path=resolved,
            backup_path=backup,
            restore_available=True,
        )
        raise ActionError(f"Disabled file already exists: {disabled.name}")
    resolved.rename(disabled)
    _record(
        "disable_launch_agent",
        resolved,
        "success",
        f"Renamed to {disabled.name}; backup at {backup}",
        target_type="launch_agent",
        target_path=disabled,
        backup_path=backup,
        restore_available=True,
    )
    return disabled


def enable_launch_agent(path: str | Path) -> Path:
    """Re-enable a previously disabled user LaunchAgent plist."""
    try:
        p = Path(path).expanduser().resolve()
    except OSError as exc:
        raise ActionError(str(exc)) from exc
    if p.name.endswith(".plist.disabled"):
        enabled = Path(str(p)[: -len(".disabled")])
    elif p.suffix == ".disabled":
        enabled = p.with_suffix("")
    else:
        candidate = Path(str(p) + ".disabled")
        if candidate.exists():
            enabled = p
            p = candidate
        else:
            raise ActionError("Target is not a disabled LaunchAgent plist.")
    if enabled.exists():
        raise ActionError(f"Enabled plist already exists: {enabled.name}")
    if is_protected_path(str(p)) or is_protected_path(str(enabled)):
        raise ActionError("Protected path.")
    home_agents = Path.home() / "Library" / "LaunchAgents"
    if p.parent != home_agents:
        raise ActionError("Only user LaunchAgents can be re-enabled in Version 1.")
    p.rename(enabled)
    args = ["launchctl", "bootstrap", _launch_domain(), str(enabled)]
    rc, out, err = run_command(args, timeout=30)
    message = out or err
    _record(
        "enable_launch_agent",
        enabled,
        "success" if rc == 0 else "partial",
        message,
        target_type="launch_agent",
        target_path=enabled,
        command=args,
        exit_code=rc,
        stdout=out,
        stderr=err,
    )
    if rc != 0:
        raise ActionError(
            f"Plist restored to {enabled.name}, but launchctl bootstrap failed: {message or 'unknown error'}"
        )
    return enabled


def reveal_in_finder(path: str | Path) -> None:
    resolved = _resolve_path(path)
    if not resolved.exists():
        raise ActionError("Path does not exist.")
    args = ["open", "-R", str(resolved)]
    _run_recorded(
        "reveal_in_finder",
        resolved,
        args,
        target_type="path",
        target_path=resolved,
        timeout=15,
    )


def system_launch_item_instructions(path: str) -> str:
    """Return administrator workflow instructions; no elevation is performed."""
    return (
        f"System LaunchAgent/Daemon management requires administrator privileges.\n\n"
        f"Target: {path}\n\n"
        f"In Version 1, {APP_NAME} does not collect passwords or perform privilege elevation.\n"
        f"To manage this item manually:\n"
        f"  1. Review the plist carefully.\n"
        f"  2. Back it up.\n"
        f"  3. Use `sudo launchctl bootout system {path}` only if you understand the impact.\n"
        f"Actions for system launch items remain unavailable inside {APP_NAME}."
    )


def stop_brew_service(name: str) -> None:
    args = brew_cmd("services", "stop", name)
    _run_recorded(
        "stop_brew_service",
        name,
        args,
        target_type="brew_service",
        timeout=60,
    )


def start_brew_service(name: str) -> None:
    args = brew_cmd("services", "start", name)
    _run_recorded(
        "start_brew_service",
        name,
        args,
        target_type="brew_service",
        timeout=60,
    )


def restart_brew_service(name: str) -> None:
    args = brew_cmd("services", "restart", name)
    _run_recorded(
        "restart_brew_service",
        name,
        args,
        target_type="brew_service",
        timeout=60,
    )


def brew_autostart_enable(name: str) -> None:
    """Register a Homebrew service to start automatically at login."""
    args = brew_cmd("services", "start", name)
    _run_recorded(
        "brew_autostart_enable",
        name,
        args,
        target_type="brew_service",
        timeout=60,
    )


def brew_autostart_disable(name: str) -> None:
    """Disable automatic startup for a Homebrew service."""
    _require_destructive()
    args = brew_cmd("services", "stop", name)
    _run_recorded(
        "brew_autostart_disable",
        name,
        args,
        target_type="brew_service",
        timeout=60,
    )


def brew_upgrade(name: str, *, cask: bool = False) -> None:
    """Upgrade a Homebrew formula or cask."""
    _require_destructive()
    args = brew_cmd("upgrade", *(["--cask"] if cask else []), name)
    _run_recorded(
        "brew_upgrade",
        name,
        args,
        target_type="brew_cask" if cask else "brew_formula",
        timeout=300,
    )


def brew_cleanup_preview() -> str:
    """Return dry-run output from `brew cleanup -n`."""
    args = brew_cmd("cleanup", "-n")
    rc, out, err = run_command(args, timeout=120)
    preview = out or err or "No cleanup candidates reported."
    _record(
        "brew_cleanup_preview",
        "brew",
        "success" if rc == 0 else "failed",
        preview,
        target_type="brew",
        command=args,
        exit_code=rc,
        stdout=out,
        stderr=err,
    )
    if rc != 0:
        raise ActionError(preview)
    return preview


def brew_dependency_review(name: str, *, cask: bool = False) -> str:
    """Return dependency information for uninstall confirmation."""
    if cask:
        args = brew_cmd("info", "--cask", "--json=v2", name)
    else:
        args = brew_cmd("info", "--json=v2", name)
    rc, out, err = run_command(args, timeout=60)
    if rc != 0:
        return err or out or "Unable to retrieve dependency information."
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        return out
    lines: list[str] = []
    key = "casks" if cask else "formulae"
    entries = payload.get(key) or []
    if not entries:
        return out
    entry = entries[0]
    deps = entry.get("dependencies") or entry.get("depends_on") or []
    installed_on = entry.get("installed_on_request")
    lines.append(f"Package: {name} ({'cask' if cask else 'formula'})")
    if isinstance(deps, list) and deps:
        lines.append("Dependencies: " + ", ".join(str(d) for d in deps))
    elif isinstance(deps, dict):
        lines.append("Depends on: " + json.dumps(deps))
    else:
        lines.append("No declared dependencies listed.")
    uses_args = brew_cmd("uses", "--installed", name)
    urc, uout, _ = run_command(uses_args, timeout=60)
    if urc == 0 and uout.strip():
        lines.append("Installed packages that depend on this: " + ", ".join(uout.splitlines()))
    else:
        lines.append("No installed packages report a dependency on this item.")
    if installed_on is not None:
        lines.append(f"Installed on request: {installed_on}")
    return "\n".join(lines)


def uninstall_brew(name: str, cask: bool = False) -> None:
    _require_destructive()
    args = brew_cmd("uninstall", *(["--cask"] if cask else []), name)
    _run_recorded(
        "uninstall_brew",
        name,
        args,
        target_type="brew_cask" if cask else "brew_formula",
        timeout=120,
    )


def open_application(path: str | Path) -> None:
    """Open an application bundle."""
    ok, reason, resolved = validate_app_bundle_target(path)
    if not ok or resolved is None:
        try:
            resolved = _resolve_path(path)
        except ActionError as exc:
            raise ActionError(reason or str(exc)) from exc
        if not resolved.exists() or resolved.suffix != ".app":
            raise ActionError(reason or "Invalid application.")
        if is_protected_path(str(resolved)):
            raise ActionError("Protected application.")
    args = ["open", str(resolved)]
    _run_recorded(
        "open_application",
        resolved,
        args,
        target_type="application",
        target_path=resolved,
        timeout=30,
    )


def quit_application(path: str | Path) -> None:
    """Ask a running application to quit via AppleScript bundle id / name."""
    ok, reason, resolved = validate_app_bundle_target(path)
    if not ok or resolved is None:
        try:
            resolved = _resolve_path(path)
        except ActionError as exc:
            raise ActionError(reason or str(exc)) from exc
        if not resolved.exists() or resolved.suffix != ".app":
            raise ActionError(reason or "Invalid application.")
        if is_protected_path(str(resolved)):
            raise ActionError("Protected application.")
    script = f'tell application "{resolved.stem}" to quit'
    args = ["osascript", "-e", script]
    _run_recorded(
        "quit_application",
        resolved,
        args,
        target_type="application",
        target_path=resolved,
        timeout=30,
    )


def force_quit_application(path: str | Path) -> None:
    """Force-quit an application after destructive-action confirmation."""
    _require_destructive()
    ok, reason, resolved = validate_app_bundle_target(path)
    if not ok or resolved is None:
        try:
            resolved = _resolve_path(path)
        except ActionError as exc:
            raise ActionError(reason or str(exc)) from exc
        if not resolved.exists() or resolved.suffix != ".app":
            raise ActionError(reason or "Invalid application.")
        if is_protected_path(str(resolved)):
            raise ActionError("Protected application.")
    script = f'tell application "{resolved.stem}" to quit'
    args = ["osascript", "-e", script]
    rc, out, err = run_command(args, timeout=30)
    if rc != 0:
        kill_args = ["killall", resolved.stem]
        _run_recorded(
            "force_quit_application",
            resolved,
            kill_args,
            target_type="application",
            target_path=resolved,
            timeout=30,
        )
        return
    _record(
        "force_quit_application",
        resolved,
        "success",
        out or err or "Quit requested",
        target_type="application",
        target_path=resolved,
        command=args,
        exit_code=rc,
        stdout=out,
        stderr=err,
    )


def move_app_to_trash(path: str | Path) -> Path:
    """Move an application bundle to Trash without deleting support files."""
    _require_destructive()
    ok, reason, resolved = validate_app_bundle_target(path)
    if not ok or resolved is None:
        _record(
            "move_app_to_trash",
            path,
            "blocked",
            reason,
            target_type="application",
            target_path=path,
        )
        raise ActionError(reason)
    destination = _move_to_trash(resolved)
    _record(
        "move_app_to_trash",
        resolved,
        "success",
        str(destination),
        target_type="application",
        target_path=resolved,
    )
    return destination


def trash_path(path: str | Path, allowed_roots: list[str | Path]) -> Path:
    """Move a reviewed cleanup target to Trash when it is within allowed roots."""
    _require_destructive()
    resolved = _validate_cleanup_path(path, allowed_roots)
    settings = load_settings()
    if not settings.prefer_trash and resolved.is_file():
        destination = move_to_disabled_items(resolved)
    else:
        destination = _move_to_trash(resolved)
    _record(
        "trash_path",
        resolved,
        "success",
        str(destination),
        target_type="path",
        target_path=resolved,
    )
    return destination


def delete_venv(path: str | Path) -> None:
    """Delete a Python virtual environment after validation."""
    _require_destructive()
    resolved = _validate_venv_target(path)
    shutil.rmtree(resolved)
    _record(
        "delete_venv",
        resolved,
        "success",
        "Virtual environment removed",
        target_type="venv",
        target_path=resolved,
    )


def remove_conda_env(name: str) -> None:
    """Remove a Conda environment by name or path."""
    _require_destructive()
    if "MacScope" in name or name.strip() in {"base"}:
        raise ActionError("Protected Conda environment.")
    conda = shutil.which("conda")
    if not conda:
        raise ActionError("Conda not found on PATH.")
    flag = "-p" if ("/" in name or name.startswith("~")) else "-n"
    args = [conda, "env", "remove", flag, name, "--yes"]
    _run_recorded(
        "remove_conda_env",
        name,
        args,
        target_type="conda_env",
        timeout=180,
    )


def remove_pyenv_version(version: str) -> None:
    """Remove an installed pyenv-managed Python version."""
    _require_destructive()
    pyenv = shutil.which("pyenv")
    if not pyenv:
        raise ActionError("pyenv not found on PATH.")
    version_dir = Path.home() / ".pyenv" / "versions" / version
    if is_protected_path(str(version_dir)):
        raise ActionError("Protected pyenv version path.")
    args = [pyenv, "uninstall", "-f", version]
    _run_recorded(
        "remove_pyenv_version",
        version,
        args,
        target_type="pyenv_version",
        timeout=180,
    )


def remove_node_modules(path: str | Path) -> None:
    """Remove a project node_modules directory after validation."""
    _require_destructive()
    resolved = _validate_node_modules_target(path)
    shutil.rmtree(resolved)
    _record(
        "remove_node_modules",
        resolved,
        "success",
        "node_modules removed",
        target_type="node_modules",
        target_path=resolved,
    )


def uninstall_npm_global(name: str) -> None:
    """Uninstall a globally installed npm package."""
    _require_destructive()
    npm = shutil.which("npm")
    if not npm:
        raise ActionError("npm not found on PATH.")
    args = [npm, "uninstall", "-g", name]
    _run_recorded(
        "uninstall_npm_global",
        name,
        args,
        target_type="npm_global",
        timeout=120,
    )


def docker_start(name_or_id: str) -> None:
    args = docker_cmd("start", name_or_id)
    _run_recorded(
        "docker_start",
        name_or_id,
        args,
        target_type="docker_container",
        timeout=60,
    )


def docker_stop(name_or_id: str) -> None:
    args = docker_cmd("stop", name_or_id)
    _run_recorded(
        "docker_stop",
        name_or_id,
        args,
        target_type="docker_container",
        timeout=60,
    )


def docker_restart(name_or_id: str) -> None:
    args = docker_cmd("restart", name_or_id)
    _run_recorded(
        "docker_restart",
        name_or_id,
        args,
        target_type="docker_container",
        timeout=60,
    )


def docker_remove_container(name_or_id: str) -> None:
    _require_destructive()
    args = docker_cmd("rm", "-f", name_or_id)
    _run_recorded(
        "docker_remove_container",
        name_or_id,
        args,
        target_type="docker_container",
        timeout=60,
    )


def docker_remove_image(image: str) -> None:
    _require_destructive()
    args = docker_cmd("rmi", "-f", image)
    _run_recorded(
        "docker_remove_image",
        image,
        args,
        target_type="docker_image",
        timeout=120,
    )


def docker_prune_preview() -> dict[str, str]:
    """Return reclaimable Docker disk usage by category."""
    args = docker_cmd("system", "df", "--format", "{{json .}}")
    rc, out, err = run_command(args, timeout=60)
    preview: dict[str, str] = {}
    if rc == 0:
        for line in out.splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            category = str(row.get("Type", "")).lower()
            if category:
                preview[category] = str(row.get("Reclaimable") or row.get("Size") or "")
    else:
        preview["error"] = err or out or "docker system df failed"
    _record(
        "docker_prune_preview",
        "docker",
        "success" if rc == 0 else "failed",
        json.dumps(preview),
        target_type="docker",
        command=args,
        exit_code=rc,
        stdout=out,
        stderr=err,
    )
    if rc != 0:
        raise ActionError(preview.get("error", "docker system df failed"))
    return preview


def docker_prune_selected(categories: list[str]) -> dict[str, str]:
    """Prune selected Docker resource categories."""
    _require_destructive()
    if not categories:
        raise ActionError("No Docker prune categories selected.")
    unknown = [c for c in categories if c not in _DOCKER_PRUNE_CATEGORIES]
    if unknown:
        raise ActionError(f"Unknown Docker prune categories: {', '.join(unknown)}")
    results: dict[str, str] = {}
    command_map = {
        "containers": docker_cmd("container", "prune", "-f"),
        "images": docker_cmd("image", "prune", "-f"),
        "volumes": docker_cmd("volume", "prune", "-f"),
        "networks": docker_cmd("network", "prune", "-f"),
        "build-cache": docker_cmd("builder", "prune", "-f"),
    }
    for category in categories:
        args = command_map[category]
        rc, out, err = run_command(args, timeout=180)
        message = out or err or ("ok" if rc == 0 else "failed")
        results[category] = message
        _record(
            "docker_prune_selected",
            category,
            "success" if rc == 0 else "failed",
            message,
            target_type="docker",
            command=args,
            exit_code=rc,
            stdout=out,
            stderr=err,
        )
        if rc != 0:
            raise ActionError(f"Docker prune failed for {category}: {message}")
    return results

