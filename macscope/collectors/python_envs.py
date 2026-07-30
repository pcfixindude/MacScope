from __future__ import annotations

import json
import shutil
from pathlib import Path

from inventory import Item
from macscope.settings import load_settings
from utils import dir_size_bytes, logger, run_command


class PythonCollector:
    name = "Python"

    def collect(self) -> list[Item]:
        items: list[Item] = []
        items.extend(self._interpreters())
        items.extend(self._venvs())
        items.extend(self._conda_envs())
        items.extend(self._pyenv_versions())
        return items

    def _interpreters(self) -> list[Item]:
        items: list[Item] = []
        candidates = [
            "/usr/bin/python3",
            "/opt/homebrew/bin/python3",
            "/usr/local/bin/python3",
        ]
        which = shutil.which("python3")
        if which:
            candidates.append(which)
        seen: set[str] = set()
        for path in candidates:
            p = Path(path)
            if not p.exists():
                continue
            resolved = str(p.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            rc, out, _ = run_command([resolved, "--version"], timeout=10)
            version = out if rc == 0 else None
            protected = resolved.startswith("/usr/bin/") or "MacScope" in resolved
            item = Item(
                category="Python",
                name=f"Python interpreter ({p.name})",
                path=resolved,
                status="Installed",
                version=version,
                vendor="Python",
                item_type="Interpreter",
                subtype="system" if protected else "local",
                executable_path=resolved,
                installation_source="System" if protected else "Local",
                protected=protected,
                risk="Protected" if protected else "Safe",
                explanation=f"Python interpreter at {resolved}.",
                details={"kind": "interpreter"},
            )
            item.ensure_stable_id()
            items.append(item)
        return items

    def _venvs(self) -> list[Item]:
        settings = load_settings()
        items: list[Item] = []
        depth = max(1, min(settings.scan_depth, 6))
        for root in settings.project_scan_roots:
            base = Path(root).expanduser()
            if not base.exists():
                continue
            try:
                for pyvenv in base.glob("*/**/.venv/pyvenv.cfg"):
                    # Bound depth
                    rel = pyvenv.relative_to(base)
                    if len(rel.parts) > depth + 1:
                        continue
                    env = pyvenv.parent
                    items.append(self._venv_item(env, base))
                    if len(items) > 200:
                        return items
                for cfg in base.glob("*/**/bin/activate"):
                    env = cfg.parent.parent
                    if (env / "pyvenv.cfg").exists():
                        continue
                    rel = cfg.relative_to(base)
                    if len(rel.parts) > depth + 2:
                        continue
                    if env.name in {".venv", "venv", "env", ".env"}:
                        items.append(self._venv_item(env, base))
            except OSError as exc:
                logger.warning("Python venv scan failed under %s: %s", base, exc)
        return items

    def _venv_item(self, env: Path, project_root: Path) -> Item:
        size = float(dir_size_bytes(env, max_files=3000))
        project = env.parent
        try:
            mtime = str(env.stat().st_mtime)
        except OSError:
            mtime = None
        python_bin = env / "bin" / "python"
        version = None
        if python_bin.exists():
            rc, out, _ = run_command([str(python_bin), "--version"], timeout=8)
            if rc == 0:
                version = out
        # Protect MacScope env
        protected = "MacScope" in str(env) or str(env).endswith("/.venv") and (env.parent / "app.py").exists()
        item = Item(
            category="Python",
            name=f"venv · {project.name}",
            path=str(env),
            status="Installed",
            version=version,
            vendor="virtualenv",
            item_type="Virtual Environment",
            subtype="venv",
            executable_path=str(python_bin) if python_bin.exists() else None,
            installation_source=str(project_root),
            related_application=project.name,
            disk_usage=size,
            modification_date=mtime,
            protected=protected,
            risk="Protected" if protected else "Caution",
            explanation=f"Python virtual environment for project '{project.name}'.",
            removal_guidance="Delete only after confirming the project no longer needs this environment.",
            available_actions=["Reveal environment", "Copy activation command", "Delete virtual environment"]
            if not protected
            else ["Reveal environment", "Copy activation command"],
            details={
                "project": str(project),
                "activate": f"source {env}/bin/activate",
                "kind": "venv",
            },
        )
        item.ensure_stable_id()
        return item

    def _conda_envs(self) -> list[Item]:
        items: list[Item] = []
        conda = shutil.which("conda")
        if not conda:
            return items
        rc, out, err = run_command([conda, "env", "list", "--json"], timeout=30)
        if rc != 0:
            logger.info("conda env list unavailable: %s", err or out)
            return items
        try:
            payload = json.loads(out)
        except json.JSONDecodeError:
            return items
        for env_path in payload.get("envs") or []:
            p = Path(env_path)
            name = p.name
            protected = name in {"base"} or "MacScope" in str(p)
            item = Item(
                category="Python",
                name=f"conda · {name}",
                path=str(p),
                status="Installed",
                vendor="Conda",
                item_type="Conda Environment",
                subtype="conda",
                installation_source="Conda",
                protected=protected,
                risk="Protected" if protected else "Caution",
                explanation=f"Conda environment '{name}'.",
                available_actions=["Reveal environment", "Remove Conda environment"]
                if not protected
                else ["Reveal environment"],
                details={"kind": "conda", "conda": conda},
            )
            item.ensure_stable_id()
            items.append(item)
        return items

    def _pyenv_versions(self) -> list[Item]:
        items: list[Item] = []
        pyenv = shutil.which("pyenv")
        root = Path.home() / ".pyenv" / "versions"
        if not root.exists():
            return items
        try:
            for version_dir in sorted(root.iterdir()):
                if not version_dir.is_dir():
                    continue
                item = Item(
                    category="Python",
                    name=f"pyenv · {version_dir.name}",
                    path=str(version_dir),
                    status="Installed",
                    version=version_dir.name,
                    vendor="pyenv",
                    item_type="pyenv Version",
                    subtype="pyenv",
                    installation_source="pyenv",
                    risk="Caution",
                    explanation=f"pyenv-managed Python {version_dir.name}.",
                    available_actions=["Reveal environment", "Remove pyenv version"]
                    if pyenv
                    else ["Reveal environment"],
                    details={"kind": "pyenv", "pyenv": pyenv},
                )
                item.ensure_stable_id()
                items.append(item)
        except OSError as exc:
            logger.warning("pyenv scan failed: %s", exc)
        return items
