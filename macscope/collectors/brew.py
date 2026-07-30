from __future__ import annotations

import shutil

from inventory import Item
from utils import logger, run_command


class BrewCollector:
    name = "Homebrew"

    def collect(self) -> list[Item]:
        if not shutil.which("brew"):
            logger.info("Homebrew not found; skipping BrewCollector")
            return []
        items: list[Item] = []
        items.extend(self._list_packages("Formula", ["brew", "list", "--formula"]))
        items.extend(self._list_packages("Cask", ["brew", "list", "--cask"]))
        items.extend(self._list_services())
        return items

    def _list_packages(self, kind: str, args: list[str]) -> list[Item]:
        rc, out, err = run_command(args, timeout=60)
        if rc != 0:
            logger.warning("brew list %s failed: %s", kind, err or out)
            return []
        items: list[Item] = []
        for name in out.splitlines():
            name = name.strip()
            if not name:
                continue
            items.append(
                Item(
                    category="Homebrew",
                    name=name,
                    path=None,
                    status="Installed",
                    vendor=kind,
                    version=None,
                    risk="Safe",
                    protected=False,
                    label=name,
                    item_type=kind,
                    executable_path=None,
                    publisher="Homebrew",
                    installation_source="Homebrew",
                    running_state=None,
                    startup_state=None,
                    related_application=name,
                    explanation=f"Homebrew {kind.lower()} '{name}'.",
                    details={"kind": kind},
                )
            )
        return items

    def _list_services(self) -> list[Item]:
        rc, out, err = run_command(["brew", "services", "list"], timeout=30)
        if rc != 0:
            logger.warning("brew services list failed: %s", err or out)
            return []
        items: list[Item] = []
        lines = out.splitlines()
        if not lines:
            return items
        for line in lines[1:]:
            parts = line.split()
            if not parts:
                continue
            name = parts[0]
            status = parts[1] if len(parts) > 1 else "unknown"
            user = parts[2] if len(parts) > 2 else ""
            running = status.lower() == "started"
            items.append(
                Item(
                    category="Services",
                    name=name,
                    path=None,
                    status=status,
                    vendor="Homebrew",
                    version=None,
                    risk="Caution",
                    protected=False,
                    label=name,
                    item_type="Homebrew Service",
                    executable_path=None,
                    publisher="Homebrew",
                    installation_source="Homebrew",
                    running_state="Running" if running else "Stopped",
                    startup_state="enabled" if running else status,
                    related_application=name,
                    explanation=f"Homebrew service '{name}' ({status}).",
                    details={"raw": line, "user": user},
                )
            )
        return items
