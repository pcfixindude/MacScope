from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from inventory import Item
from utils import logger


class CrashReportsCollector:
    name = "Crashes"

    roots = [
        Path.home() / "Library" / "Logs" / "DiagnosticReports",
        Path("/Library/Logs/DiagnosticReports"),
    ]

    def collect(self) -> list[Item]:
        groups: dict[str, list[Path]] = defaultdict(list)
        for root in self.roots:
            if not root.exists():
                continue
            try:
                for path in root.glob("*.ips"):
                    app = _app_from_crash_name(path.name)
                    groups[app].append(path)
                for path in root.glob("*.crash"):
                    app = _app_from_crash_name(path.name)
                    groups[app].append(path)
            except OSError as exc:
                logger.warning("Crash report scan failed for %s: %s", root, exc)
        items: list[Item] = []
        for app, paths in sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True):
            times = []
            for path in paths:
                try:
                    times.append(datetime.fromtimestamp(path.stat().st_mtime))
                except OSError:
                    continue
            times.sort(reverse=True)
            item = Item(
                category="Crashes",
                name=app,
                path=str(paths[0].parent),
                status=f"{len(paths)} report(s)",
                item_type="Crash History",
                risk="Caution" if len(paths) >= 3 else "Unknown",
                explanation=f"{app} has {len(paths)} local crash report(s).",
                modification_date=str(times[0].timestamp()) if times else None,
                details={
                    "count": len(paths),
                    "recent": [t.isoformat(sep=" ", timespec="seconds") for t in times[:10]],
                    "files": [p.name for p in paths[:20]],
                },
            )
            item.ensure_stable_id()
            items.append(item)
        return items


def _app_from_crash_name(name: str) -> str:
    # Example: AppName-2024-01-01-120000.ips
    base = Path(name).stem
    match = re.match(r"^(.*?)-\d{4}-\d{2}-\d{2}", base)
    if match:
        return match.group(1)
    return base.split("-")[0] or base
