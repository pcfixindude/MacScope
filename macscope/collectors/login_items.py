from __future__ import annotations

import re
from pathlib import Path

from inventory import Item
from utils import logger, path_exists, run_command


class LoginItemsCollector:
    """Collect login items and macOS background task management entries where accessible."""

    name = "Login & Background Items"

    def collect(self) -> list[Item]:
        items: list[Item] = []
        items.extend(self._login_items_via_osascript())
        items.extend(self._background_items_via_sfltool())
        return items

    def _login_items_via_osascript(self) -> list[Item]:
        items: list[Item] = []
        rc, out, err = run_command(
            [
                "osascript",
                "-e",
                'tell application "System Events" to get the name of every login item',
            ],
            timeout=20,
        )
        if rc != 0:
            logger.warning("Login items via System Events unavailable: %s", err or out)
            return items
        if not out or out.strip() == "":
            return items
        # osascript returns comma-separated names
        names = [n.strip() for n in out.split(",") if n.strip()]
        paths_rc, paths_out, _ = run_command(
            [
                "osascript",
                "-e",
                'tell application "System Events" to get the path of every login item',
            ],
            timeout=20,
        )
        paths: list[str] = []
        if paths_rc == 0 and paths_out:
            paths = [p.strip() for p in paths_out.split(", ")]
            # Fallback split on comma if needed
            if len(paths) != len(names) and "," in paths_out:
                paths = [p.strip() for p in paths_out.split(",")]

        for index, name in enumerate(names):
            path = paths[index] if index < len(paths) else None
            missing = bool(path and not path_exists(path))
            items.append(
                Item(
                    category="Login Items",
                    name=name,
                    path=path,
                    status="Configured",
                    vendor="Login Item",
                    risk="Orphaned" if missing else "Caution",
                    protected=False,
                    label=None,
                    item_type="Login Item",
                    executable_path=path,
                    publisher=None,
                    installation_source="User Login Items",
                    running_state=None,
                    startup_state="login item",
                    related_application=name,
                    explanation=(
                        "The referenced executable does not exist. This may be an orphaned startup item."
                        if missing
                        else f"Starts a user {name} application at login."
                    ),
                    details={"source": "System Events"},
                )
            )
        return items

    def _background_items_via_sfltool(self) -> list[Item]:
        """Parse `sfltool dumpbtm` when available (macOS Ventura+)."""
        items: list[Item] = []
        rc, out, err = run_command(["sfltool", "dumpbtm"], timeout=45)
        if rc != 0:
            logger.info("sfltool dumpbtm unavailable: %s", err or out)
            return items
        if not out:
            return items

        # Heuristic parse: look for UUID blocks with name / URL / type fields
        blocks = re.split(r"\n(?=UUID:)", out)
        for block in blocks:
            if "UUID:" not in block:
                continue
            name_match = re.search(r"(?:Name|Bundle Identifier):\s*(.+)", block)
            url_match = re.search(r"(?:URL|Path):\s*(?:file://)?(.+)", block)
            type_match = re.search(r"Type:\s*(.+)", block)
            name = (name_match.group(1).strip() if name_match else None) or "Background Item"
            raw_path = url_match.group(1).strip() if url_match else None
            if raw_path:
                raw_path = raw_path.rstrip("/")
                if raw_path.startswith("file://"):
                    raw_path = raw_path[7:]
            item_type = type_match.group(1).strip() if type_match else "Background Item"
            # Skip obvious Apple system noise if under /System
            protected = bool(raw_path and str(raw_path).startswith("/System/"))
            missing = bool(raw_path and not Path(raw_path).exists())
            items.append(
                Item(
                    category="Background Items",
                    name=name,
                    path=raw_path,
                    status="Configured",
                    vendor="BackgroundItems",
                    risk="Protected" if protected else ("Orphaned" if missing else "Caution"),
                    protected=protected,
                    label=name if "." in name else None,
                    item_type=item_type,
                    executable_path=raw_path,
                    publisher=None,
                    installation_source="Background Task Management",
                    running_state=None,
                    startup_state="background item",
                    related_application=name.split(".")[-1] if "." in name else name,
                    explanation=(
                        "Apple system component. Management actions are disabled."
                        if protected
                        else (
                            "The referenced executable does not exist. This may be an orphaned startup item."
                            if missing
                            else f"macOS background item associated with {name}."
                        )
                    ),
                    details={"source": "sfltool dumpbtm", "raw_type": item_type},
                )
            )
        return items
