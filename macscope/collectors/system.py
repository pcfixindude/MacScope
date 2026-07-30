from __future__ import annotations

import platform
import shutil
from pathlib import Path

import psutil

from inventory import Item
from utils import run_command


class SystemCollector:
    name = "System"

    def collect(self) -> list[Item]:
        vm = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        items: list[Item] = [
            Item(
                category="System",
                name="macOS",
                status=platform.mac_ver()[0],
                risk="Protected",
                protected=True,
                item_type="Operating System",
                classification="Apple protected",
                explanation="Apple system component. Management actions are disabled.",
                details={"platform": platform.platform()},
            ),
            Item(
                category="Performance",
                name="Memory",
                status=f"{vm.percent}% used",
                risk="Protected",
                protected=True,
                item_type="Performance",
                classification="Apple protected",
                explanation="Current memory pressure summary.",
                details={"total": vm.total, "used": vm.used, "available": vm.available},
                memory=float(vm.percent),
            ),
            Item(
                category="Performance",
                name="CPU",
                status=f"{psutil.cpu_percent(interval=0.2)}% used",
                risk="Protected",
                protected=True,
                item_type="Performance",
                classification="Apple protected",
                explanation="Current CPU utilization sample.",
                details={"cores": psutil.cpu_count()},
            ),
            Item(
                category="Storage",
                name="Root Disk",
                status=f"{disk.percent}% used",
                risk="Protected",
                protected=True,
                item_type="Storage",
                classification="Apple protected",
                explanation="Root volume usage.",
                details={"total": disk.total, "used": disk.used, "free": disk.free},
                disk_usage=float(disk.used),
            ),
        ]
        checks: list[tuple[str, list[str]]] = [
            ("SIP", ["csrutil", "status"]),
            ("Gatekeeper", ["spctl", "--status"]),
            ("FileVault", ["fdesetup", "status"]),
            (
                "Firewall",
                ["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"],
            ),
        ]
        for title, cmd in checks:
            binary = cmd[0]
            if binary.startswith("/"):
                if not Path(binary).exists():
                    continue
            elif not shutil.which(binary):
                continue
            _, out, err = run_command(cmd, timeout=10)
            items.append(
                Item(
                    category="Security",
                    name=title,
                    status=out or err or "Unavailable",
                    risk="Protected",
                    protected=True,
                    item_type="Security Status",
                    classification="Apple protected",
                    explanation=f"{title} status from local macOS tooling.",
                    details={"command": " ".join(cmd)},
                    removal_guidance="Review or adjust in System Settings when appropriate.",
                )
            )
        # Sharing-related status via launchctl print-disabled / defaults where possible
        for title, label in (
            ("Remote Login (SSH)", "com.openssh.sshd"),
            ("Screen Sharing", "com.apple.screensharing"),
        ):
            rc, out, err = run_command(["launchctl", "print-disabled", "system"], timeout=10)
            text = out or err
            status = "Unknown"
            if rc == 0 and label in text:
                # lines look like: "com.openssh.sshd" => disabled/enabled
                for line in text.splitlines():
                    if label in line:
                        status = "disabled" if "true" in line.lower() or "disabled" in line.lower() else line.strip()
                        break
            items.append(
                Item(
                    category="Security",
                    name=title,
                    status=status,
                    risk="Protected",
                    protected=True,
                    item_type="Sharing Status",
                    classification="Apple protected",
                    explanation=f"{title} configuration summary. Manage in System Settings > General > Sharing.",
                    details={"label": label},
                )
            )
        for item in items:
            item.ensure_stable_id()
        return items
