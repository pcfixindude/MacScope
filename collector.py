from __future__ import annotations

import time
from dataclasses import dataclass, field

from identifier import enrich_items
from inventory import Item
from macscope.collectors.applications import ApplicationsCollector
from macscope.collectors.ai_models import AICollector
from macscope.collectors.brew import BrewCollector
from macscope.collectors.crashes import CrashReportsCollector
from macscope.collectors.docker_env import DockerCollector
from macscope.collectors.launch import LaunchItemsCollector
from macscope.collectors.login_items import LoginItemsCollector
from macscope.collectors.network import NetworkCollector
from macscope.collectors.node_envs import NodeCollector
from macscope.collectors.permissions import PermissionsCollector
from macscope.collectors.processes import ProcessesCollector
from macscope.collectors.python_envs import PythonCollector
from macscope.collectors.storage import StorageCollector
from macscope.collectors.system import SystemCollector
from macscope.knowledge import enrich_item_knowledge
from macscope.projects import discover_projects, link_inventory_to_projects, projects_as_items
from macscope.relationships import Relation, build_relationships
from macscope.settings import load_settings
from macscope.startup_analyzer import annotate_startup_impacts
from utils import logger


ALL_COLLECTORS = [
    ApplicationsCollector(),
    ProcessesCollector(),
    LaunchItemsCollector(),
    LoginItemsCollector(),
    BrewCollector(),
    NetworkCollector(),
    SystemCollector(),
    PythonCollector(),
    NodeCollector(),
    DockerCollector(),
    AICollector(),
    StorageCollector(),
    CrashReportsCollector(),
    PermissionsCollector(),
]


@dataclass
class CollectionResult:
    items: list[Item] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    relationships: list[Relation] = field(default_factory=list)
    duration_seconds: float = 0.0


def collect_all(progress=None, *, deep: bool = False) -> CollectionResult:
    """Run collectors; continue when individual collectors fail."""
    started = time.time()
    result = CollectionResult()
    settings = load_settings()
    enabled = settings.collectors_enabled or {}
    collectors = []
    for collector in ALL_COLLECTORS:
        key = collector.name
        settings_key = {
            "Startup Items": "Startup",
            "Login & Background Items": "Login Items",
            "Homebrew": "Homebrew",
            "AI": "AI",
            "Crashes": "Crashes",
            "Permissions": "Permissions",
        }.get(key, key)
        if key == "Docker" and not settings.collect_docker:
            continue
        if key == "AI" and not settings.collect_ai_models:
            continue
        if key == "Network" and not settings.collect_network_listeners:
            continue
        if enabled.get(settings_key, True) is False:
            continue
        collectors.append(collector)

    total = max(len(collectors) + 1, 1)
    for index, collector in enumerate(collectors, 1):
        if progress:
            progress((index - 1) / total, f"Collecting {collector.name}…")
        try:
            collected = collector.collect()
            result.items.extend(collected)
        except Exception as exc:
            logger.exception("Collector %s failed: %s", collector.name, exc)
            result.errors.append({"collector": collector.name, "error": str(exc)})

    if progress:
        progress(0.85, "Discovering projects…")
    try:
        projects = discover_projects()
        result.items.extend(projects_as_items(projects))
        project_rels = link_inventory_to_projects(result.items, projects)
    except Exception as exc:
        logger.exception("Project discovery failed: %s", exc)
        result.errors.append({"collector": "Projects", "error": str(exc)})
        project_rels = []

    if progress:
        progress(0.92, "Identifying and linking…")
    try:
        _cross_link_running_apps(result.items)
        result.items = enrich_items(result.items)
        for item in result.items:
            enrich_item_knowledge(item)
            item.ensure_stable_id()
        annotate_startup_impacts(result.items)
        result.relationships = build_relationships(result.items) + project_rels
    except Exception as exc:
        logger.exception("Post-processing failed: %s", exc)
        result.errors.append({"collector": "Post-processing", "error": str(exc)})
    result.duration_seconds = time.time() - started
    if progress:
        progress(1.0, "Complete")
    return result


def _cross_link_running_apps(items: list[Item]) -> None:
    running_apps: set[str] = set()
    ports_by_name: dict[str, list[str]] = {}
    for item in items:
        if item.category == "Processes" and item.path and "/Applications/" in item.path:
            for part in item.path.split("/"):
                if part.endswith(".app"):
                    running_apps.add(part[:-4])
        if item.category == "Network" and item.network_ports:
            ports_by_name.setdefault(item.name, []).append(item.network_ports)
    for item in items:
        if item.category == "Applications":
            item.running_state = "Running" if item.name in running_apps else "Not running"
            if item.name in ports_by_name:
                item.network_ports = ", ".join(ports_by_name[item.name])
