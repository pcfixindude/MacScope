from __future__ import annotations

"""Startup impact scoring from observed process metrics and launch configuration."""

from inventory import Item


def score_startup_impact(item: Item, processes: list[Item] | None = None) -> str:
    """Return Low / Medium / High for startup-related items."""
    if item.category not in {"Startup", "Login Items", "Background Items"}:
        return item.startup_impact or "Low"

    score = 0
    details = item.details or {}
    if details.get("run_at_load") or (item.startup_state or "").lower() in {"enabled", "login item", "background item"}:
        score += 2
    if details.get("keep_alive"):
        score += 2
    if details.get("start_interval") or details.get("StartInterval"):
        score += 1
    if item.orphan_status or item.classification == "Orphaned":
        return "Low"

    # Match related running process resource use
    processes = processes or []
    related_name = (item.related_application or item.name or "").lower()
    label = (item.label or "").lower()
    cpu = 0.0
    mem = 0.0
    for proc in processes:
        pname = (proc.name or "").lower()
        if pname and (pname in related_name or pname in label or (item.related_application and item.related_application.lower() in pname)):
            cpu = max(cpu, float(proc.cpu or 0))
            mem = max(mem, float(proc.memory or 0))
    if cpu >= 5 or mem >= 2:
        score += 3
    elif cpu >= 1 or mem >= 0.5:
        score += 1

    if item.vendor and "Apple" in str(item.vendor):
        score = max(0, score - 1)
    if "/Library/LaunchDaemons" in (item.path or ""):
        score += 1

    if score >= 5:
        return "High"
    if score >= 3:
        return "Medium"
    return "Low"


def annotate_startup_impacts(items: list[Item]) -> None:
    processes = [i for i in items if i.category == "Processes"]
    for item in items:
        if item.category in {"Startup", "Login Items", "Background Items"}:
            item.startup_impact = score_startup_impact(item, processes)
