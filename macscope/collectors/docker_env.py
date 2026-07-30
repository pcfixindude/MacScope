from __future__ import annotations

import json
import shutil

from inventory import Item
from utils import logger, run_command


class DockerCollector:
    name = "Docker"

    def collect(self) -> list[Item]:
        docker = shutil.which("docker")
        if not docker:
            return [
                Item(
                    category="Docker",
                    name="Docker",
                    status="Not installed",
                    item_type="Runtime",
                    risk="Unknown",
                    explanation="Docker CLI was not found on PATH.",
                    details={"available": False},
                )
            ]
        # Daemon check
        rc, out, err = run_command([docker, "info", "--format", "{{json .}}"], timeout=20)
        if rc != 0:
            return [
                Item(
                    category="Docker",
                    name="Docker daemon",
                    status="Not running",
                    item_type="Runtime",
                    path=docker,
                    risk="Caution",
                    explanation="Docker is installed but the daemon is not running.",
                    details={"available": True, "daemon": False, "error": err or out},
                )
            ]
        items: list[Item] = []
        items.append(
            Item(
                category="Docker",
                name="Docker daemon",
                status="Running",
                item_type="Runtime",
                path=docker,
                running_state="Running",
                risk="Safe",
                explanation="Docker daemon is reachable.",
                details={"available": True, "daemon": True},
            )
        )
        items.extend(self._containers(docker))
        items.extend(self._images(docker))
        items.extend(self._volumes(docker))
        items.extend(self._networks(docker))
        # Disk usage summary
        drc, dout, _ = run_command([docker, "system", "df", "--format", "{{json .}}"], timeout=30)
        if drc == 0 and dout:
            for line in dout.splitlines():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                items.append(
                    Item(
                        category="Docker",
                        name=f"Disk · {row.get('Type', 'unknown')}",
                        status=str(row.get("Size", "")),
                        item_type="Disk Usage",
                        disk_usage=None,
                        risk="Caution",
                        explanation=f"Docker {row.get('Type')} usage: {row.get('Size')} (reclaimable {row.get('Reclaimable')}).",
                        details=row,
                    )
                )
        for item in items:
            item.category = "Docker"
            item.ensure_stable_id()
        return items

    def _containers(self, docker: str) -> list[Item]:
        rc, out, err = run_command(
            [docker, "ps", "-a", "--format", "{{json .}}"],
            timeout=30,
        )
        if rc != 0:
            logger.warning("docker ps failed: %s", err or out)
            return []
        items: list[Item] = []
        for line in out.splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            name = row.get("Names") or row.get("ID")
            state = row.get("State") or row.get("Status")
            ports = row.get("Ports")
            item = Item(
                category="Docker",
                name=str(name),
                path=None,
                status=str(state),
                item_type="Container",
                subtype="container",
                label=row.get("ID"),
                network_ports=str(ports) if ports else None,
                running_state="Running" if str(state).lower() == "running" else "Stopped",
                risk="Caution",
                explanation=f"Docker container '{name}' ({state}).",
                available_actions=["Start container", "Stop container", "Restart container", "Remove stopped container", "Show inspect data"],
                details=row,
            )
            items.append(item)
        return items

    def _images(self, docker: str) -> list[Item]:
        rc, out, err = run_command([docker, "images", "--format", "{{json .}}"], timeout=30)
        if rc != 0:
            logger.warning("docker images failed: %s", err or out)
            return []
        items: list[Item] = []
        for line in out.splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            name = f"{row.get('Repository', '')}:{row.get('Tag', '')}"
            item = Item(
                category="Docker",
                name=name,
                status="Installed",
                item_type="Image",
                subtype="image",
                label=row.get("ID"),
                risk="Caution",
                explanation=f"Docker image {name}.",
                available_actions=["Remove image", "Show inspect data"],
                details=row,
            )
            items.append(item)
        return items

    def _volumes(self, docker: str) -> list[Item]:
        rc, out, _ = run_command([docker, "volume", "ls", "--format", "{{json .}}"], timeout=30)
        if rc != 0:
            return []
        items: list[Item] = []
        for line in out.splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            item = Item(
                category="Docker",
                name=str(row.get("Name")),
                status="Configured",
                item_type="Volume",
                subtype="volume",
                risk="Caution",
                explanation=f"Docker volume '{row.get('Name')}'.",
                available_actions=["Remove unused volume"],
                details=row,
            )
            items.append(item)
        return items

    def _networks(self, docker: str) -> list[Item]:
        rc, out, _ = run_command([docker, "network", "ls", "--format", "{{json .}}"], timeout=30)
        if rc != 0:
            return []
        items: list[Item] = []
        for line in out.splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            name = str(row.get("Name"))
            protected = name in {"bridge", "host", "none"}
            item = Item(
                category="Docker",
                name=name,
                status="Configured",
                item_type="Network",
                subtype="network",
                protected=protected,
                risk="Protected" if protected else "Caution",
                explanation=f"Docker network '{name}'.",
                available_actions=[] if protected else ["Remove unused network"],
                details=row,
            )
            items.append(item)
        return items
