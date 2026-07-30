from __future__ import annotations

from pathlib import Path

import psutil

from inventory import Item
from utils import dir_size_bytes, format_bytes, logger


class StorageCollector:
    name = "Storage"

    def collect(self) -> list[Item]:
        items: list[Item] = []
        disk = psutil.disk_usage("/")
        items.append(
            Item(
                category="Storage",
                name="Root volume",
                status=f"{disk.percent}% used",
                item_type="Volume",
                disk_usage=float(disk.used),
                protected=True,
                risk="Protected",
                explanation=f"System volume: {format_bytes(disk.used)} used of {format_bytes(disk.total)}.",
                details={"total": disk.total, "used": disk.used, "free": disk.free},
            )
        )
        home = Path.home()
        targets = [
            ("Home folder", home, 3000),
            ("Applications", Path("/Applications"), 2000),
            ("Downloads", home / "Downloads", 4000),
            ("Caches", home / "Library" / "Caches", 4000),
            ("Logs", home / "Library" / "Logs", 3000),
            ("Trash", home / ".Trash", 2000),
            ("Docker data", home / "Library" / "Containers" / "com.docker.docker", 2000),
            ("MacScope data", home / "Library" / "Application Support" / "MacScope", 2000),
        ]
        for name, path, limit in targets:
            if not path.exists():
                continue
            try:
                size = float(dir_size_bytes(path, max_files=limit))
            except OSError as exc:
                logger.warning("Storage scan failed for %s: %s", path, exc)
                continue
            item = Item(
                category="Storage",
                name=name,
                path=str(path),
                status=format_bytes(size),
                item_type="Folder Usage",
                disk_usage=size,
                risk="Caution" if name in {"Caches", "Logs", "Trash", "Downloads"} else "Safe",
                protected=name in {"Home folder", "MacScope data"},
                explanation=f"{name} uses approximately {format_bytes(size)} (bounded scan).",
                available_actions=["Reveal in Finder"]
                if name not in {"Home folder"}
                else [],
                details={"bounded_scan": True, "max_files": limit},
            )
            item.ensure_stable_id()
            items.append(item)
        for item in items:
            item.ensure_stable_id()
        return items
