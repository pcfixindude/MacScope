from __future__ import annotations

"""Collector plugin architecture — wraps existing collectors without duplication."""

from dataclasses import dataclass, field
from typing import Any, Callable

from inventory import Item
from macscope.collectors.base import Collector
from utils import logger


@dataclass
class PluginMeta:
    id: str
    name: str
    description: str
    version: str = "1.0"
    categories: tuple[str, ...] = ()
    provides_actions: bool = False
    provides_timeline: bool = True
    provides_reports: bool = True
    provides_assistant: bool = True


@dataclass
class Plugin:
    meta: PluginMeta
    collector: Collector
    actions: dict[str, Callable[..., Any]] = field(default_factory=dict)
    enabled: bool = True


_REGISTRY: list[Plugin] = []


def register_plugin(plugin: Plugin) -> None:
    if any(p.meta.id == plugin.meta.id for p in _REGISTRY):
        return
    _REGISTRY.append(plugin)


def clear_registry() -> None:
    _REGISTRY.clear()


def _wrap_collector(collector: Collector, description: str, categories: tuple[str, ...]) -> Plugin:
    return Plugin(
        meta=PluginMeta(
            id=collector.name.lower().replace(" ", "_").replace("&", "and"),
            name=collector.name,
            description=description,
            categories=categories,
        ),
        collector=collector,
    )


def bootstrap_builtin_plugins(collectors: list[Collector] | None = None) -> list[Plugin]:
    """Register built-in collectors as isolated plugins."""
    if _REGISTRY:
        return list(_REGISTRY)
    if collectors is None:
        from collector import ALL_COLLECTORS

        collectors = list(ALL_COLLECTORS)
    descriptions = {
        "Applications": "Installed applications inventory",
        "Processes": "Running process inventory",
        "Startup Items": "LaunchAgents and LaunchDaemons",
        "Login & Background Items": "Login items and background tasks",
        "Homebrew": "Brew formulas, casks, and services",
        "Network": "Listening network ports",
        "System": "Host/system facts",
        "Python": "Python interpreters and environments",
        "Node": "Node runtimes and node_modules",
        "Docker": "Containers, images, volumes",
        "AI": "Local AI apps and models",
        "Storage": "Bounded storage summaries",
        "Crashes": "Crash report groupings",
        "Permissions": "TCC permission explorer data",
    }
    categories = {
        "Applications": ("Applications",),
        "Processes": ("Processes",),
        "Startup Items": ("Startup",),
        "Login & Background Items": ("Login Items", "Background Items"),
        "Homebrew": ("Homebrew", "Services"),
        "Network": ("Network",),
        "System": ("System", "Security"),
        "Python": ("Python",),
        "Node": ("Node",),
        "Docker": ("Docker",),
        "AI": ("AI",),
        "Storage": ("Storage",),
        "Crashes": ("Crashes",),
        "Permissions": ("Permissions",),
    }
    for collector in collectors:
        register_plugin(
            _wrap_collector(
                collector,
                descriptions.get(collector.name, collector.name),
                categories.get(collector.name, ()),
            )
        )
    return list(_REGISTRY)


def list_plugins() -> list[Plugin]:
    if not _REGISTRY:
        bootstrap_builtin_plugins()
    return list(_REGISTRY)


def collect_via_plugins(progress=None) -> tuple[list[Item], list[dict[str, str]]]:
    """Run plugin collectors with isolated failure handling."""
    plugins = list_plugins()
    items: list[Item] = []
    errors: list[dict[str, str]] = []
    total = max(len(plugins), 1)
    for index, plugin in enumerate(plugins, 1):
        if not plugin.enabled:
            continue
        if progress:
            progress((index - 1) / total, f"Plugin {plugin.meta.name}…")
        try:
            items.extend(plugin.collector.collect())
        except Exception as exc:
            logger.exception("Plugin %s failed: %s", plugin.meta.id, exc)
            errors.append({"collector": plugin.meta.name, "error": str(exc), "plugin": plugin.meta.id})
    return items, errors


def plugin_manifest() -> list[dict[str, Any]]:
    return [
        {
            "id": p.meta.id,
            "name": p.meta.name,
            "description": p.meta.description,
            "version": p.meta.version,
            "categories": list(p.meta.categories),
            "enabled": p.enabled,
            "actions": sorted(p.actions),
            "timeline": p.meta.provides_timeline,
            "reports": p.meta.provides_reports,
            "assistant": p.meta.provides_assistant,
        }
        for p in list_plugins()
    ]
