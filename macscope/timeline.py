from __future__ import annotations

from datetime import datetime
from typing import Any

from database import SessionLocal
from models import TimelineEvent
from utils import json_dumps, json_loads, logger


def record_timeline(
    event_type: str,
    title: str,
    *,
    summary: str = "",
    category: str | None = None,
    stable_id: str | None = None,
    snapshot_id: int | None = None,
    source: str = "system",
    details: dict[str, Any] | None = None,
) -> None:
    try:
        with SessionLocal() as db:
            db.add(
                TimelineEvent(
                    event_type=event_type,
                    category=category,
                    title=title[:512],
                    summary=summary or "",
                    stable_id=stable_id,
                    snapshot_id=snapshot_id,
                    source=source,
                    details_json=json_dumps(details or {}),
                )
            )
            db.commit()
    except Exception as exc:
        logger.warning("Failed to record timeline event: %s", exc)


def record_action_timeline(
    action: str,
    target: object,
    result: str,
    message: str = "",
    *,
    target_type: str | None = None,
) -> None:
    record_timeline(
        event_type="management_action",
        title=f"{action}: {target}",
        summary=f"{result}. {message}".strip(),
        category=target_type,
        source="action",
        details={"action": action, "target": str(target), "result": result},
    )


def list_timeline(
    *,
    limit: int = 200,
    event_type: str | None = None,
    category: str | None = None,
) -> list[TimelineEvent]:
    with SessionLocal() as db:
        q = db.query(TimelineEvent).order_by(TimelineEvent.id.desc())
        if event_type:
            q = q.filter(TimelineEvent.event_type == event_type)
        if category:
            q = q.filter(TimelineEvent.category == category)
        return q.limit(limit).all()


def record_snapshot_delta(snapshot_id: int, older_rows: list, newer_rows: list) -> int:
    """Derive timeline events from snapshot comparison. Returns number of events."""
    from compare import compare_snapshots

    if not older_rows:
        record_timeline(
            "snapshot_created",
            f"Initial snapshot #{snapshot_id}",
            summary=f"{len(newer_rows)} items collected.",
            snapshot_id=snapshot_id,
            source="snapshot",
        )
        return 1

    result = compare_snapshots(older_rows, newer_rows)
    count = 0

    def _emit(event_type: str, category: str, entries: list, verb: str) -> None:
        nonlocal count
        for entry in entries[:200]:
            name = entry.get("Name") or entry.get("Label") or "item"
            record_timeline(
                event_type,
                f"{verb}: {name}",
                summary=entry.get("Explanation") or entry.get("Type") or "",
                category=category,
                stable_id=entry.get("Stable ID"),
                snapshot_id=snapshot_id,
                source="snapshot",
                details={"changes": entry.get("changes"), "path": entry.get("Path")},
            )
            count += 1

    _emit("software_installed", "Applications", result.new_applications, "Installed")
    _emit("software_removed", "Applications", result.removed_applications, "Removed")
    _emit("software_updated", "Applications", result.version_changes, "Updated")
    _emit("startup_changed", "Startup", result.startup_state_changes + result.newly_enabled_startup, "Startup change")
    _emit("security_changed", "Security", result.security_changes, "Security change")
    brew_added = [e for e in result.added if e.get("Category") in {"Homebrew", "Services"}]
    brew_removed = [e for e in result.removed if e.get("Category") in {"Homebrew", "Services"}]
    _emit("homebrew_changed", "Homebrew", brew_added + brew_removed + result.service_status_changes, "Homebrew change")
    docker = [e for e in result.added + result.removed + result.changed if e.get("Category") == "Docker"]
    _emit("docker_changed", "Docker", docker, "Docker change")
    python = [e for e in result.added + result.removed if e.get("Category") == "Python"]
    _emit("python_changed", "Python", python, "Python environment change")
    _emit("ai_model_changed", "AI", result.new_ai_models + result.removed_ai_models, "AI model change")
    _emit("network_changed", "Network", result.newly_opened_ports + result.closed_ports, "Network listener change")
    return count
