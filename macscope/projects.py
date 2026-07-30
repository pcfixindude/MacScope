from __future__ import annotations

"""Development project discovery and inventory grouping."""

from dataclasses import dataclass, field
from pathlib import Path

from inventory import Item
from macscope.relationships import Relation
from macscope.settings import load_settings
from macscope.stable_id import item_stable_id
from utils import logger


INDICATORS = {
    "Python": ("pyproject.toml", "requirements.txt", "setup.py", "Pipfile"),
    "Node": ("package.json", "yarn.lock", "pnpm-lock.yaml"),
    "Docker": ("Dockerfile", "docker-compose.yml", "compose.yml"),
    "Git": (".git",),
    "Streamlit": (".streamlit",),
    "SQLite": ("*.sqlite", "*.sqlite3", "*.db"),
    "PostgreSQL": ("docker-compose.yml",),  # heuristic only; refined below
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


def discover_projects() -> list[Project]:
    settings = load_settings()
    depth = max(1, min(settings.scan_depth, 5))
    projects: list[Project] = []
    seen: set[str] = set()
    for root in settings.project_scan_roots:
        base = Path(root).expanduser()
        if not base.exists():
            continue
        try:
            for child in sorted(base.iterdir()):
                if not child.is_dir() or child.name.startswith("."):
                    continue
                # Also scan one level deeper for grouped workspaces
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
                    if not indicators:
                        continue
                    key = str(project_dir.resolve())
                    if key in seen:
                        continue
                    seen.add(key)
                    stable = item_stable_id(
                        category="Projects",
                        name=project_dir.name,
                        path=key,
                    )
                    projects.append(
                        Project(
                            key=key,
                            name=project_dir.name,
                            path=key,
                            indicators=indicators,
                            stable_id=stable,
                        )
                    )
        except OSError as exc:
            logger.warning("Project discovery failed under %s: %s", base, exc)
    return projects


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
    # Streamlit apps often have app.py + streamlit in requirements
    if "Python" in found and (path / "app.py").exists():
        if "Streamlit" not in found:
            try:
                req = path / "requirements.txt"
                if req.exists() and "streamlit" in req.read_text(encoding="utf-8", errors="ignore").lower():
                    found.append("Streamlit")
            except OSError:
                pass
    # Postgres compose heuristic
    for compose_name in ("docker-compose.yml", "compose.yml"):
        compose = path / compose_name
        if compose.exists():
            try:
                text = compose.read_text(encoding="utf-8", errors="ignore").lower()
                if "postgres" in text and "PostgreSQL" not in found:
                    found.append("PostgreSQL")
            except OSError:
                pass
    return found


def projects_as_items(projects: list[Project]) -> list[Item]:
    items: list[Item] = []
    for project in projects:
        item = Item(
            category="Projects",
            name=project.name,
            path=project.path,
            status="Discovered",
            item_type="Development Project",
            subtype=",".join(project.indicators),
            installation_source="Project scan",
            project_key=project.key,
            explanation=f"Development project with indicators: {', '.join(project.indicators)}.",
            risk="Safe",
            details={"indicators": project.indicators},
            available_actions=["Reveal project", "Open project folder"],
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
            # Related application name heuristic
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
    return "project_related_item"


def group_items_by_project(items: list[Item]) -> dict[str, list[Item]]:
    grouped: dict[str, list[Item]] = {}
    for item in items:
        key = item.project_key or ""
        if not key:
            continue
        grouped.setdefault(key, []).append(item)
    return grouped
