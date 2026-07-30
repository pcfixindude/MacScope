from __future__ import annotations

from pathlib import Path
from typing import Any

from inventory import Item
from protection import executable_missing, is_protected_path
from utils import codesign_team_info, logger, parse_program_from_plist, read_plist


class LaunchItemsCollector:
    name = "Startup Items"

    roots = [
        ("User LaunchAgent", Path.home() / "Library" / "LaunchAgents", False, "User LaunchAgents"),
        ("LaunchAgent", Path("/Library/LaunchAgents"), False, "System LaunchAgents"),
        ("LaunchDaemon", Path("/Library/LaunchDaemons"), False, "System LaunchDaemons"),
        ("Apple LaunchAgent", Path("/System/Library/LaunchAgents"), True, "Apple LaunchAgents"),
        ("Apple LaunchDaemon", Path("/System/Library/LaunchDaemons"), True, "Apple LaunchDaemons"),
    ]

    def collect(self) -> list[Item]:
        items: list[Item] = []
        for vendor, root, protected, source in self.roots:
            if not root.exists():
                continue
            try:
                files = sorted(root.glob("*.plist")) + sorted(root.glob("*.plist.disabled"))
            except OSError as exc:
                logger.warning("Cannot list %s: %s", root, exc)
                continue
            for plist_path in files:
                try:
                    items.append(self._item_for_plist(plist_path, vendor, protected, source))
                except Exception as exc:
                    logger.warning("Launch item error for %s: %s", plist_path, exc)
        return items

    def _item_for_plist(
        self,
        plist_path: Path,
        vendor: str,
        protected_root: bool,
        source: str,
    ) -> Item:
        disabled = plist_path.name.endswith(".plist.disabled")
        data: dict[str, Any] = {}
        if not disabled:
            data = read_plist(plist_path)
        else:
            # Try reading disabled copy
            data = read_plist(plist_path)

        label = data.get("Label") or plist_path.name.replace(".plist.disabled", "").replace(".plist", "")
        program = parse_program_from_plist(data)
        program_args = data.get("ProgramArguments") or []
        run_at_load = bool(data.get("RunAtLoad"))
        keep_alive = bool(data.get("KeepAlive"))
        orphaned = executable_missing(program)
        protected = protected_root or is_protected_path(str(plist_path)) or (
            bool(program) and is_protected_path(program)
        )

        publisher = None
        if program and Path(program.split()[0]).exists():
            publisher = codesign_team_info(program.split()[0]).get("authority")

        related = None
        if isinstance(label, str) and "." in label:
            parts = label.split(".")
            if len(parts) >= 2 and parts[1].lower() not in {"apple", "macos"}:
                related = parts[1][:1].upper() + parts[1][1:]

        if disabled:
            startup_state = "disabled"
            status = "Disabled"
        elif run_at_load or keep_alive:
            startup_state = "enabled"
            status = "Configured"
        else:
            startup_state = "configured"
            status = "Configured"

        explanation = None
        if orphaned:
            explanation = "The referenced executable does not exist. This may be an orphaned startup item."
        elif related and "docker" in str(label).lower():
            explanation = "Launches Docker Desktop’s privileged networking helper."
        elif related and vendor == "User LaunchAgent":
            explanation = f"Starts a user {related} application at login."

        return Item(
            category="Startup",
            name=str(label),
            path=str(plist_path),
            status=status,
            vendor=vendor,
            version=None,
            risk="Protected" if protected else ("Orphaned" if orphaned else "Unknown"),
            protected=protected,
            label=str(label),
            item_type=vendor,
            executable_path=program,
            publisher=publisher,
            installation_source=source,
            running_state=None,
            startup_state=startup_state,
            related_application=related,
            explanation=explanation,
            details={
                "program": program or "",
                "program_arguments": program_args,
                "run_at_load": run_at_load,
                "keep_alive": keep_alive,
                "disabled": disabled,
                "working_directory": data.get("WorkingDirectory"),
                "username": data.get("UserName"),
            },
        )
