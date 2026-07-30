from __future__ import annotations

import os
from pathlib import Path

from config import APP_NAME, PROTECTED_PROCESS_NAMES


PROTECTED_PATH_PREFIXES = (
    "/System/",
    "/usr/bin/",
    "/usr/sbin/",
    "/bin/",
    "/sbin/",
    "/usr/libexec/",
)

PROTECTED_PATH_EXACT = frozenset(
    {
        "/sbin/launchd",
        "/usr/sbin/WindowServer",
        "/System/Library/CoreServices/loginwindow.app",
        "/System/Library/CoreServices/WindowServer.app",
    }
)


def is_protected_path(path: str | None) -> bool:
    """Return True when a path is under Apple/system-protected locations.

    Uses the logical path (expanduser only). Symlink resolution is avoided so
    items that appear under /Applications are not treated as /System paths
    solely because of macOS firmlinks.
    """
    if not path:
        return False
    try:
        normalized = str(Path(path).expanduser())
    except OSError:
        return False

    # Logical application installs are classified separately; path alone is not protected.
    try:
        home_apps = str(Path.home() / "Applications")
    except OSError:
        home_apps = ""
    if normalized.startswith("/Applications/") or (
        home_apps and normalized.startswith(home_apps + "/")
    ):
        return False

    if normalized in PROTECTED_PATH_EXACT:
        return True
    for prefix in PROTECTED_PATH_PREFIXES:
        if normalized == prefix.rstrip("/") or normalized.startswith(prefix):
            return True
    if normalized.startswith("/Library/Apple/"):
        return True
    return False


def is_apple_signed(publisher: str | None, bundle_id: str | None = None) -> bool:
    if bundle_id and bundle_id.startswith("com.apple."):
        return True
    if not publisher:
        return False
    lower = publisher.lower()
    return (
        "apple root ca" in lower
        or "apple worldwide developer relations" in lower
        or publisher.startswith("Apple ")
        or "Software Signing" in publisher
        or publisher == "Apple Code Signing Certification Authority"
        or "Developer ID Application: Apple" in publisher
    )


def is_protected_process(
    *,
    pid: int | None,
    name: str | None = None,
    exe: str | None = None,
) -> tuple[bool, str]:
    """Determine whether a process must never be stopped."""
    if pid is None:
        return True, "Process ID is missing."
    if pid in (0, 1):
        return True, "Kernel or launchd process."
    if pid == os.getpid():
        return True, f"{APP_NAME}'s own process cannot be stopped."
    try:
        parent_pid = os.getppid()
        if pid == parent_pid:
            return True, "Parent shell or Terminal launching MacScope is protected."
    except OSError:
        pass
    if name and name in PROTECTED_PROCESS_NAMES:
        return True, f"{name} is a protected system process."
    if exe and is_protected_path(exe):
        return True, "Executable is under a protected system path."
    if name and name.lower() in {"streamlit", "macscope"}:
        if pid == os.getpid() or _is_our_streamlit(pid):
            return True, f"{APP_NAME}'s own process cannot be stopped."
    return False, ""


def _is_our_streamlit(pid: int) -> bool:
    try:
        import psutil

        proc = psutil.Process(pid)
        cmdline = " ".join(proc.cmdline()).lower()
        return "app.py" in cmdline and "streamlit" in cmdline
    except Exception:
        return False


def _launch_domain(path: Path) -> str:
    """Return 'user', 'system', 'apple', or 'other' for a launch plist path."""
    text = str(path)
    if text.startswith("/System/Library/Launch"):
        return "apple"
    if text.startswith("/Library/LaunchAgents") or text.startswith("/Library/LaunchDaemons"):
        return "system"
    try:
        home_agents = Path.home() / "Library" / "LaunchAgents"
        if home_agents in path.parents or path.parent == home_agents:
            return "user"
        # Also accept disabled siblings in the same folder
        if path.parent == home_agents or str(path.parent) == str(home_agents):
            return "user"
    except OSError:
        pass
    return "other"


def validate_launch_plist_target(path: str | Path) -> tuple[bool, str, Path | None]:
    """Validate a LaunchAgent/Daemon plist before management actions."""
    try:
        p = Path(path).expanduser()
        # Resolve only for user paths we will mutate; keep logical form for domain checks.
        logical = p
        try:
            resolved = p.resolve(strict=False)
        except OSError:
            resolved = p
    except OSError as exc:
        return False, f"Cannot resolve path: {exc}", None

    domain = _launch_domain(logical)
    if domain == "apple" or is_protected_path(str(logical)):
        return False, "Apple system launch items cannot be managed.", None
    if domain == "system":
        return (
            False,
            "System launch items require administrator workflow (unavailable as an in-app elevated action).",
            None,
        )
    if domain != "user":
        return False, "Only user LaunchAgents can be managed in Version 1.", None
    if not logical.exists():
        return False, "Plist file does not exist.", None
    if logical.suffix != ".plist" and not logical.name.endswith(".plist.disabled"):
        return False, "Target is not a plist file.", None
    return True, "", resolved


def validate_app_bundle_target(path: str | Path) -> tuple[bool, str, Path | None]:
    """Validate an application bundle before Trash / Reveal actions."""
    try:
        p = Path(path).expanduser().resolve()
    except OSError as exc:
        return False, f"Cannot resolve path: {exc}", None
    if not p.exists():
        return False, "Application path does not exist.", None
    if p.suffix != ".app":
        return False, "Target is not an application bundle.", None
    # Reject system applications even when firmlinked
    logical = str(Path(path).expanduser())
    if logical.startswith("/System/") or is_protected_path(logical):
        return False, "Application is under a protected system path.", None
    allowed_parents = {Path("/Applications"), Path.home() / "Applications"}
    # Compare logical parent when possible
    logical_path = Path(path).expanduser()
    if logical_path.parent not in allowed_parents and p.parent not in allowed_parents:
        return False, "Only top-level apps in /Applications or ~/Applications can be managed.", None
    return True, "", p


def executable_missing(executable_path: str | None) -> bool:
    if not executable_path:
        return False
    candidate = executable_path.strip().split()[0]
    try:
        return not Path(candidate).expanduser().exists()
    except OSError:
        return True
