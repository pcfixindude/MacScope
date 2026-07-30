from __future__ import annotations

import sqlite3
from pathlib import Path

from inventory import Item
from utils import logger, run_command


# Human-friendly TCC service labels
SERVICE_LABELS = {
    "kTCCServiceCamera": "Camera",
    "kTCCServiceMicrophone": "Microphone",
    "kTCCServiceAccessibility": "Accessibility",
    "kTCCServiceAppleEvents": "Automation",
    "kTCCServiceListenEvent": "Input Monitoring",
    "kTCCServiceScreenCapture": "Screen Recording",
    "kTCCServiceSystemPolicyAllFiles": "Full Disk Access",
    "kTCCServiceDeveloperTool": "Developer Tools",
    "kTCCServicePostEvent": "Input Monitoring",
}


class PermissionsCollector:
    name = "Permissions"

    def collect(self) -> list[Item]:
        items: list[Item] = []
        items.extend(self._from_tcc_db(Path.home() / "Library" / "Application Support" / "com.apple.TCC" / "TCC.db", "User TCC"))
        # System TCC often requires FDA; attempt read-only and degrade gracefully
        items.extend(self._from_tcc_db(Path("/Library/Application Support/com.apple.TCC/TCC.db"), "System TCC"))
        if not items:
            items.append(
                Item(
                    category="Permissions",
                    name="Permissions unavailable",
                    status="Limited",
                    item_type="Permission",
                    risk="Unknown",
                    protected=True,
                    explanation="TCC permission databases were not readable. Grant Full Disk Access to Terminal/Python for richer results.",
                    details={"hint": "System Settings → Privacy & Security"},
                )
            )
        for item in items:
            item.ensure_stable_id()
        return items

    def _from_tcc_db(self, db_path: Path, source: str) -> list[Item]:
        if not db_path.exists():
            return []
        items: list[Item] = []
        try:
            # Read-only URI
            uri = f"file:{db_path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True, timeout=5)
            try:
                cur = conn.execute(
                    "SELECT service, client, auth_value FROM access ORDER BY service, client"
                )
                rows = cur.fetchall()
            finally:
                conn.close()
        except Exception as exc:
            logger.info("TCC read failed for %s: %s", db_path, exc)
            return []

        for service, client, auth_value in rows:
            label = SERVICE_LABELS.get(service)
            if not label:
                continue
            allowed = auth_value in (1, 2)  # allowed / allowed limited depending on macOS
            items.append(
                Item(
                    category="Permissions",
                    name=f"{label} · {client}",
                    path=str(db_path),
                    status="Allowed" if allowed else "Not allowed",
                    item_type=label,
                    subtype=service,
                    label=client,
                    installation_source=source,
                    risk="Caution" if allowed and label in {"Full Disk Access", "Accessibility", "Screen Recording"} else "Safe",
                    explanation=f"{client} {'has' if allowed else 'does not have'} {label} permission ({source}).",
                    details={"service": service, "client": client, "auth_value": auth_value, "source": source},
                )
            )
        return items
