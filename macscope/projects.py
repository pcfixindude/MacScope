from __future__ import annotations

"""Development project discovery, intelligence enrichment, and inventory grouping."""

import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from inventory import Item
from macscope.relationships import Relation
from macscope.settings import load_settings
from macscope.stable_id import item_stable_id
from utils import format_bytes, logger


INDICATORS = {
    "Python": ("pyproject.toml", "requirements.txt", "setup.py", "Pipfile", "poetry.lock"),
    "Node": ("package.json", "yarn.lock", "pnpm-lock.yaml", "package-lock.json"),
    "Docker": ("Dockerfile", "docker-compose.yml", "compose.yml", "docker-compose.yaml"),
    "Git": (".git",),
    "Streamlit": (".streamlit",),
    "SQLite": ("*.sqlite", "*.sqlite3", "*.db"),
    "PostgreSQL": ("docker-compose.yml",),
    "Cursor": (".cursor",),
    "VS Code": (".vscode",),
}


@dataclass
class Project:
    key: str
    name: str
    path: str
    indicators: list[str] = field(default_factory=list)
    stable_id: str = ""
    # Intelligence fields (V4)
    git_branch: str | None = None
    git_status: str | None = None
    last_commit: str | None = None
    readme: str | None = None
    license: str | None = None
    requirements: list[str] = field(default_factory=list)
    package_files: list[str] = field(default_factory=list)
    project_size: float | None = None
    recent_activity: str | None = None
    pinned: bool = False
    details: dict[str, Any] = field(default_factory=dict)


def discover_projects() -> list[Project]:
    settings = load_settings()
    depth = max(1, min(settings.scan_depth, 5))
    pinned = set(settings.pinned_project_keys or [])
    projects: list[Project] = []
    seen: set[str] = set()
    for root in settings.all_project_roots():
        base = Path(root).expanduser()
        if not base.exists():
            continue
        try:
            for child in sorted(base.iterdir()):
                if not child.is_dir() or child.name.startswith("."):
                    continue
                candidates = [child]
                try:
                    for nested in child.iterdir():
                        if nested.is_dir() and not nested.name.startswith("."):
                            candidates.append(nested)
                except OSError:
                    pass
                for project_dir in candidates:
                    rel_parts = project_dir.relative_to(base).parts
                    if len(rel_parts) > depth:
                        continue
                    indicators = _detect_indicators(project_dir)
                    key = str(project_dir.resolve())
                    if not indicators and key not in pinned:
                        continue
                    if key in seen:
                        continue
                    seen.add(key)
                    stable = item_stable_id(category="Projects", name=project_dir.name, path=key)
                    project = Project(
                        key=key,
                        name=project_dir.name,
                        path=key,
                        indicators=indicators or ["Pinned"],
                        stable_id=stable,
                        pinned=key in pinned,
                    )
                    enrich_project_intelligence(project)
                    projects.append(project)
        except OSError as exc:
            logger.warning("Project discovery failed under %s: %s", base, exc)

    # Ensure manually pinned paths that are outside scan roots still appear
    for key in pinned:
        if key in seen:
            continue
        path = Path(key)
        if not path.exists():
            continue
        stable = item_stable_id(category="Projects", name=path.name, path=key)
        project = Project(
            key=key,
            name=path.name,
            path=key,
            indicators=_detect_indicators(path) or ["Pinned"],
            stable_id=stable,
            pinned=True,
        )
        enrich_project_intelligence(project)
        projects.append(project)
        seen.add(key)
    return projects


def enrich_project_intelligence(project: Project) -> Project:
    """Populate git/readme/license/size/package metadata for a project."""
    path = Path(project.path)
    if not path.exists():
        return project
    project.package_files = _list_package_files(path)
    project.requirements = _read_requirements(path)
    project.readme = _first_existing(path, ("README.md", "README.rst", "README.txt", "README"))
    project.license = _first_existing(path, ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"))
    project.project_size = _dir_size_bounded(path)
    project.recent_activity = _recent_mtime(path)
    if (path / ".git").exists():
        project.git_branch = _git(path, ["rev-parse", "--abbrev-ref", "HEAD"])
        status = _git(path, ["status", "--porcelain"])
        if status is None:
            project.git_status = "unknown"
        elif status.strip() == "":
            project.git_status = "clean"
        else:
            project.git_status = f"dirty ({len(status.splitlines())} changes)"
        project.last_commit = _git(path, ["log", "-1", "--format=%h %s (%cr)"])
    project.details = {
        "git_branch": project.git_branch,
        "git_status": project.git_status,
        "last_commit": project.last_commit,
        "readme": project.readme,
        "license": project.license,
        "requirements": project.requirements[:40],
        "package_files": project.package_files,
        "project_size": project.project_size,
        "recent_activity": project.recent_activity,
        "pinned": project.pinned,
    }
    return project


def pin_project(project_key: str) -> None:
    settings = load_settings()
    keys = list(settings.pinned_project_keys or [])
    if project_key not in keys:
        keys.append(project_key)
        from macscope.settings import update_settings

        update_settings(pinned_project_keys=keys)


def unpin_project(project_key: str) -> None:
    settings = load_settings()
    keys = [k for k in (settings.pinned_project_keys or []) if k != project_key]
    from macscope.settings import update_settings

    update_settings(pinned_project_keys=keys)


def _detect_indicators(path: Path) -> list[str]:
    found: list[str] = []
    for label, names in INDICATORS.items():
        for name in names:
            if "*" in name:
                if any(path.glob(name)):
                    found.append(label)
                    break
            else:
                if (path / name).exists():
                    found.append(label)
                    break
    if "Python" in found and (path / "app.py").exists():
        if "Streamlit" not in found:
            try:
                req = path / "requirements.txt"
                if req.exists() and "streamlit" in req.read_text(encoding="utf-8", errors="ignore").lower():
                    found.append("Streamlit")
            except OSError:
                pass
    for compose_name in ("docker-compose.yml", "compose.yml", "docker-compose.yaml"):
        compose = path / compose_name
        if compose.exists():
            try:
                text = compose.read_text(encoding="utf-8", errors="ignore").lower()
                if "postgres" in text and "PostgreSQL" not in found:
                    found.append("PostgreSQL")
            except OSError:
                pass
    return found


def _list_package_files(path: Path) -> list[str]:
    names = [
        "requirements.txt",
        "pyproject.toml",
        "package.json",
        "Pipfile",
        "poetry.lock",
        "Dockerfile",
        "docker-compose.yml",
        "compose.yml",
        "environment.yml",
        "setup.py",
    ]
    return [n for n in names if (path / n).exists()]


def _read_requirements(path: Path) -> list[str]:
    req = path / "requirements.txt"
    if not req.exists():
        return []
    try:
        lines = []
        for line in req.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(line)
        return lines[:80]
    except OSError:
        return []


def _first_existing(path: Path, names: tuple[str, ...]) -> str | None:
    for name in names:
        candidate = path / name
        if candidate.exists():
            return str(candidate)
    return None


def _dir_size_bounded(path: Path, limit_files: int = 4000) -> float | None:
    total = 0
    count = 0
    try:
        for child in path.rglob("*"):
            if child.is_symlink():
                continue
            if child.is_file():
                try:
                    total += child.stat().st_size
                except OSError:
                    continue
                count += 1
                if count >= limit_files:
                    break
        return float(total)
    except OSError:
        return None


def _recent_mtime(path: Path) -> str | None:
    newest = None
    try:
        for child in list(path.iterdir())[:80]:
            try:
                mtime = child.stat().st_mtime
                if newest is None or mtime > newest:
                    newest = mtime
            except OSError:
                continue
        if newest is None:
            newest = path.stat().st_mtime
        return datetime.fromtimestamp(newest).isoformat(sep=" ", timespec="seconds")
    except OSError:
        return None


def _git(path: Path, args: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), *args],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
        if completed.returncode != 0:
            return None
        return (completed.stdout or "").strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def projects_as_items(projects: list[Project]) -> list[Item]:
    items: list[Item] = []
    for project in projects:
        size_note = format_bytes(project.project_size) if project.project_size else "—"
        item = Item(
            category="Projects",
            name=project.name,
            path=project.path,
            status=project.git_status or "Discovered",
            item_type="Development Project",
            subtype=",".join(project.indicators),
            installation_source="Project scan",
            project_key=project.key,
            version=project.git_branch,
            disk_usage=project.project_size,
            modification_date=project.recent_activity,
            explanation=(
                f"Development project with indicators: {', '.join(project.indicators)}. "
                f"Size≈{size_note}. Branch={project.git_branch or 'n/a'}."
            ),
            risk="Safe",
            details={
                "indicators": project.indicators,
                **project.details,
            },
            available_actions=["Reveal project", "Open project folder", "Pin project", "Unpin project"],
        )
        item.stable_id = project.stable_id
        items.append(item)
    return items


def link_inventory_to_projects(items: list[Item], projects: list[Project]) -> list[Relation]:
    """Annotate items with project_key and build project relationships."""
    relations: list[Relation] = []
    by_path = sorted(projects, key=lambda p: len(p.path), reverse=True)
    for item in items:
        if item.category == "Projects":
            continue
        path = item.path or item.executable_path or ""
        matched = None
        for project in by_path:
            if path.startswith(project.path + "/") or path == project.path:
                matched = project
                break
            if item.related_application and item.related_application.lower() == project.name.lower():
                matched = project
                break
        if not matched:
            continue
        item.project_key = matched.key
        item.ensure_stable_id()
        relations.append(
            Relation(
                matched.stable_id,
                item.stable_id or "",
                _relation_type_for(item),
                0.75,
                f"Path/name association with project {matched.name}",
                matched.name,
                item.name,
            )
        )
    return relations


def project_inventory_summary(items: list[Item], project_key: str) -> dict[str, list[Item]]:
    """Group related inventory families for a single project."""
    related = [i for i in items if i.project_key == project_key or (i.category == "Projects" and i.project_key == project_key)]
    buckets: dict[str, list[Item]] = {
        "applications": [],
        "processes": [],
        "ports": [],
        "virtual_environments": [],
        "containers": [],
        "databases": [],
        "ai_models": [],
        "startup_items": [],
        "homebrew_services": [],
        "other": [],
    }
    for item in related:
        if item.category == "Projects":
            continue
        if item.category == "Applications":
            buckets["applications"].append(item)
        elif item.category == "Processes":
            buckets["processes"].append(item)
        elif item.category == "Network":
            buckets["ports"].append(item)
        elif item.category == "Python" and item.subtype in {"venv", "conda"}:
            buckets["virtual_environments"].append(item)
        elif item.category == "Docker" and item.item_type == "Container":
            buckets["containers"].append(item)
        elif "sqlite" in (item.subtype or "").lower() or (item.path or "").endswith((".db", ".sqlite", ".sqlite3")):
            buckets["databases"].append(item)
        elif item.category == "AI":
            buckets["ai_models"].append(item)
        elif item.category in {"Startup", "Login Items", "Background Items"}:
            buckets["startup_items"].append(item)
        elif item.category in {"Homebrew", "Services"}:
            buckets["homebrew_services"].append(item)
        else:
            buckets["other"].append(item)
    return buckets


def _relation_type_for(item: Item) -> str:
    if item.category == "Python" and item.subtype in {"venv", "conda"}:
        return "project_uses_virtual_environment"
    if item.category == "Docker" and item.item_type == "Container":
        return "project_uses_docker_container"
    if item.category == "Network":
        return "project_opens_port"
    if item.category == "AI":
        return "project_uses_ai_model"
    if item.category == "Processes":
        return "project_runs_process"
    if "sqlite" in (item.subtype or "").lower() or (item.path or "").endswith((".db", ".sqlite", ".sqlite3")):
        return "project_uses_database"
    if item.category in {"Startup", "Login Items", "Background Items"}:
        return "project_uses_launch_agent"
    if item.category in {"Homebrew", "Services"}:
        return "project_uses_homebrew_service"
    return "project_related_item"


def group_items_by_project(items: list[Item]) -> dict[str, list[Item]]:
    grouped: dict[str, list[Item]] = {}
    for item in items:
        key = item.project_key or ""
        if not key:
            continue
        grouped.setdefault(key, []).append(item)
    return grouped
