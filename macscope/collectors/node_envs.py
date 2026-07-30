from __future__ import annotations

import json
import shutil
from pathlib import Path

from inventory import Item
from macscope.settings import load_settings
from utils import dir_size_bytes, logger, run_command


class NodeCollector:
    name = "Node"

    def collect(self) -> list[Item]:
        items: list[Item] = []
        items.extend(self._runtimes())
        items.extend(self._global_packages())
        items.extend(self._project_modules())
        return items

    def _runtimes(self) -> list[Item]:
        items: list[Item] = []
        node = shutil.which("node")
        npm = shutil.which("npm")
        for name, path in (("node", node), ("npm", npm), ("nvm", shutil.which("nvm")), ("fnm", shutil.which("fnm")), ("volta", shutil.which("volta"))):
            if not path:
                # nvm is often a shell function
                nvm_dir = Path.home() / ".nvm"
                if name == "nvm" and nvm_dir.exists():
                    item = Item(
                        category="Node",
                        name="nvm",
                        path=str(nvm_dir),
                        status="Installed",
                        item_type="Version Manager",
                        subtype="nvm",
                        installation_source="nvm",
                        risk="Safe",
                        explanation="Node Version Manager installation detected.",
                        details={"kind": "nvm"},
                    )
                    item.ensure_stable_id()
                    items.append(item)
                continue
            version = None
            if name in {"node", "npm"}:
                rc, out, _ = run_command([path, "--version"], timeout=10)
                version = out if rc == 0 else None
            item = Item(
                category="Node",
                name=name,
                path=path,
                status="Installed",
                version=version,
                item_type="Runtime" if name == "node" else "Tool",
                subtype=name,
                executable_path=path,
                installation_source="PATH",
                risk="Safe",
                explanation=f"{name} available at {path}.",
                details={"kind": name},
            )
            item.ensure_stable_id()
            items.append(item)
        return items

    def _global_packages(self) -> list[Item]:
        items: list[Item] = []
        npm = shutil.which("npm")
        if not npm:
            return items
        rc, out, err = run_command([npm, "list", "-g", "--depth=0", "--json"], timeout=45)
        if rc not in (0, 1) or not out:
            logger.info("npm list -g failed: %s", err or out)
            return items
        try:
            payload = json.loads(out)
        except json.JSONDecodeError:
            return items
        deps = payload.get("dependencies") or {}
        for name, meta in deps.items():
            version = meta.get("version") if isinstance(meta, dict) else None
            item = Item(
                category="Node",
                name=name,
                path=None,
                status="Installed",
                version=str(version) if version else None,
                vendor="npm",
                item_type="Global Package",
                subtype="npm-global",
                installation_source="npm global",
                risk="Caution",
                explanation=f"Global npm package '{name}'.",
                available_actions=["Uninstall global npm package"],
                details={"kind": "npm-global"},
            )
            item.ensure_stable_id()
            items.append(item)
        return items

    def _project_modules(self) -> list[Item]:
        settings = load_settings()
        items: list[Item] = []
        depth = max(1, min(settings.scan_depth, 5))
        for root in settings.project_scan_roots:
            base = Path(root).expanduser()
            if not base.exists():
                continue
            try:
                for modules in base.glob("*/**/node_modules"):
                    if not modules.is_dir():
                        continue
                    # Only top-level project node_modules (not nested)
                    if modules.parent.name == "node_modules":
                        continue
                    rel = modules.relative_to(base)
                    if len(rel.parts) > depth + 1:
                        continue
                    project = modules.parent
                    lock = None
                    for candidate in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml"):
                        if (project / candidate).exists():
                            lock = candidate
                            break
                    size = float(dir_size_bytes(modules, max_files=4000))
                    try:
                        mtime = str(modules.stat().st_mtime)
                    except OSError:
                        mtime = None
                    item = Item(
                        category="Node",
                        name=f"node_modules · {project.name}",
                        path=str(modules),
                        status="Installed",
                        item_type="Project Modules",
                        subtype="node_modules",
                        installation_source=str(base),
                        related_application=project.name,
                        disk_usage=size,
                        modification_date=mtime,
                        risk="Caution",
                        explanation=f"Project node_modules for '{project.name}'.",
                        removal_guidance="Safe to remove; reinstall with npm/yarn/pnpm install.",
                        available_actions=["Reveal project", "Copy reinstall command", "Remove node_modules"],
                        details={
                            "project": str(project),
                            "lockfile": lock,
                            "reinstall": "npm install" if lock != "yarn.lock" else "yarn install",
                        },
                    )
                    item.ensure_stable_id()
                    items.append(item)
                    if len(items) > 150:
                        return items
            except OSError as exc:
                logger.warning("node_modules scan failed under %s: %s", base, exc)
        return items
