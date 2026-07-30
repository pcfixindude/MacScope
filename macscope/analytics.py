from __future__ import annotations

"""Visual analytics helpers — chart-ready frames from local data."""

from typing import Any

import pandas as pd

from macscope.storage_explorer import treemap_dataframe
from macscope.timeline import list_timeline
from macscope.usage import application_launch_frequency, usage_series
from snapshot import get_relationships


def timeline_chart_frame(days: int = 30) -> pd.DataFrame:
    events = list_timeline(limit=1000)
    if not events:
        return pd.DataFrame(columns=["date", "event_type", "count"])
    rows = []
    for event in events:
        if not event.created_at:
            continue
        rows.append({"date": event.created_at.date().isoformat(), "event_type": event.event_type})
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.groupby(["date", "event_type"], as_index=False).size().rename(columns={"size": "count"})


def usage_chart_frames(days: int = 30) -> dict[str, pd.DataFrame]:
    system = pd.DataFrame(usage_series("system", "host", days=days))
    launches = pd.DataFrame(application_launch_frequency(days=days))
    return {"system": system, "launches": launches}


def relationship_graph_frame(snapshot_id: int) -> pd.DataFrame:
    rels = get_relationships(snapshot_id)
    return pd.DataFrame(
        [
            {
                "source": r.source_stable_id,
                "target": r.target_stable_id,
                "relation_type": r.relation_type,
                "confidence": r.confidence,
                "evidence": r.evidence,
            }
            for r in rels
        ]
    )


def project_dependency_frame(rows: list[Any]) -> pd.DataFrame:
    data = []
    projects = {r.project_key or r.path: r.name for r in rows if r.category == "Projects"}
    for row in rows:
        if not getattr(row, "project_key", None):
            continue
        if row.category == "Projects":
            continue
        data.append(
            {
                "project": projects.get(row.project_key, row.project_key),
                "project_key": row.project_key,
                "item": row.name,
                "category": row.category,
                "relation": row.item_type or row.subtype or row.category,
            }
        )
    return pd.DataFrame(data)


def storage_treemap_frame(rows: list[Any]) -> pd.DataFrame:
    from macscope.storage_explorer import build_storage_tree

    # rows may be ORM inventory rows; convert lightly for size/category fields
    class _Shim:
        def __init__(self, row: Any):
            self.category = getattr(row, "category", None)
            self.name = getattr(row, "name", None)
            self.path = getattr(row, "path", None)
            self.disk_usage = getattr(row, "disk_usage", None)

    nodes = build_storage_tree([_Shim(r) for r in rows])
    return pd.DataFrame(treemap_dataframe(nodes))


def workspace_map_frame(workspaces: list[Any], members_by_id: dict[int, list[Any]]) -> pd.DataFrame:
    data = []
    for ws in workspaces:
        for member in members_by_id.get(ws.id, []):
            data.append(
                {
                    "workspace": ws.name,
                    "status": ws.status,
                    "health": ws.health,
                    "member_type": member.member_type,
                    "member": member.label or member.value,
                }
            )
    return pd.DataFrame(data)


def developer_dashboard_metrics(rows: list[Any], workspaces: list[Any] | None = None) -> dict[str, Any]:
    workspaces = workspaces or []
    return {
        "Projects": len([r for r in rows if r.category == "Projects"]),
        "Repositories": len([r for r in rows if r.category == "Projects" and "Git" in (r.subtype or "")]),
        "Branches": len({r.version for r in rows if r.category == "Projects" and r.version}),
        "Containers": len([r for r in rows if r.category == "Docker" and r.item_type == "Container"]),
        "Databases": len(
            [
                r
                for r in rows
                if "postgres" in (r.name or "").lower()
                or "sqlite" in (r.subtype or "").lower()
                or (r.path or "").endswith((".db", ".sqlite", ".sqlite3"))
            ]
        ),
        "Virtual envs": len([r for r in rows if r.category == "Python" and r.subtype in {"venv", "conda"}]),
        "AI servers": len([r for r in rows if r.category == "AI" and (r.network_ports or r.item_type == "Server")]),
        "Ports": len([r for r in rows if r.category == "Network"]),
        "Workspaces": len(workspaces),
        "Running workspaces": len([w for w in workspaces if getattr(w, "status", "") == "running"]),
    }
