from __future__ import annotations

import socket
from typing import Any

from database import SessionLocal
from inventory import Item
from models import InventoryItem, Relationship, Snapshot
from utils import json_dumps, json_loads


def _item_to_row(snapshot_id: int, item: Item) -> InventoryItem:
    item.ensure_stable_id()
    return InventoryItem(
        snapshot_id=snapshot_id,
        category=item.category,
        name=item.name,
        path=item.path,
        status=item.status,
        vendor=item.vendor,
        version=item.version,
        cpu=item.cpu,
        memory=item.memory,
        risk=item.risk,
        protected=item.protected,
        details_json=json_dumps(item.details),
        label=item.label,
        item_type=item.item_type,
        executable_path=item.executable_path,
        publisher=item.publisher,
        installation_source=item.installation_source,
        running_state=item.running_state,
        startup_state=item.startup_state,
        network_ports=item.network_ports,
        classification=item.classification,
        explanation=item.explanation,
        related_application=item.related_application,
        available_actions=json_dumps(item.available_actions),
        stable_id=item.stable_id,
        technical_name=item.technical_name,
        subtype=item.subtype,
        bundle_id=item.bundle_id,
        signing_identity=item.signing_identity or item.publisher,
        team_identifier=item.team_identifier,
        configuration_path=item.configuration_path,
        command=item.command,
        user_owner=item.user_owner,
        group_owner=item.group_owner,
        enabled_status=item.enabled_status,
        pid=item.pid,
        parent_process=item.parent_process,
        disk_usage=item.disk_usage,
        install_date=item.install_date,
        modification_date=item.modification_date,
        confidence=item.confidence,
        removal_guidance=item.removal_guidance,
        orphan_status=bool(item.orphan_status or item.classification == "Orphaned"),
        build_number=item.build_number,
        related_package=item.related_package,
        related_service=item.related_service,
        project_key=item.project_key,
        startup_impact=item.startup_impact,
        knowledge_key=item.knowledge_key,
        workspace_id=item.workspace_id,
        usage_score=item.usage_score,
        last_used_at=item.last_used_at,
    )


def save_snapshot(
    items: list[Item],
    note: str = "",
    collector_errors: list[dict[str, str]] | None = None,
    relationships: list | None = None,
    name: str | None = None,
    duration_seconds: float | None = None,
) -> int:
    # Capture previous snapshot for timeline deltas before inserting the new one.
    older_snap, older_rows = latest_snapshot()
    with SessionLocal() as db:
        snap = Snapshot(
            hostname=socket.gethostname(),
            note=note,
            name=name,
            collector_errors=json_dumps(collector_errors or []),
            duration_seconds=duration_seconds,
        )
        db.add(snap)
        db.flush()
        db.add_all([_item_to_row(snap.id, item) for item in items])
        if relationships:
            for rel in relationships:
                db.add(
                    Relationship(
                        snapshot_id=snap.id,
                        source_stable_id=rel.source_stable_id,
                        target_stable_id=rel.target_stable_id,
                        relation_type=rel.relation_type,
                        confidence=rel.confidence,
                        evidence=rel.evidence,
                    )
                )
        db.commit()
        new_id = snap.id
    try:
        from macscope.timeline import record_snapshot_delta

        _, newer_rows = get_snapshot(new_id)
        record_snapshot_delta(new_id, older_rows if older_snap else [], newer_rows)
    except Exception:
        pass
    try:
        from macscope.settings import load_settings
        from macscope.usage import record_usage_from_snapshot

        if load_settings().enable_usage_tracking:
            record_usage_from_snapshot(new_id, items)
    except Exception:
        pass
    try:
        from macscope.automation import run_due_rules

        run_due_rules(inventory_rows=items)
    except Exception:
        pass
    try:
        from macscope.cache import cache_invalidate

        cache_invalidate()
    except Exception:
        pass
    return new_id


def latest_snapshot() -> tuple[Snapshot | None, list[InventoryItem]]:
    with SessionLocal() as db:
        snap = db.query(Snapshot).order_by(Snapshot.id.desc()).first()
        if not snap:
            return None, []
        items = db.query(InventoryItem).filter_by(snapshot_id=snap.id).all()
        return snap, items


def get_snapshot(snapshot_id: int) -> tuple[Snapshot | None, list[InventoryItem]]:
    with SessionLocal() as db:
        snap = db.query(Snapshot).filter_by(id=snapshot_id).first()
        if not snap:
            return None, []
        items = db.query(InventoryItem).filter_by(snapshot_id=snap.id).all()
        return snap, items


def list_snapshots() -> list[Snapshot]:
    with SessionLocal() as db:
        return db.query(Snapshot).order_by(Snapshot.id.desc()).all()


def delete_snapshot(snapshot_id: int) -> None:
    with SessionLocal() as db:
        db.query(InventoryItem).filter_by(snapshot_id=snapshot_id).delete()
        db.query(Relationship).filter_by(snapshot_id=snapshot_id).delete()
        db.query(Snapshot).filter_by(id=snapshot_id).delete()
        db.commit()


def get_relationships(snapshot_id: int) -> list[Relationship]:
    with SessionLocal() as db:
        return db.query(Relationship).filter_by(snapshot_id=snapshot_id).all()


def row_identity_key(row: InventoryItem) -> str:
    if getattr(row, "stable_id", None):
        return row.stable_id
    details = json_loads(row.details_json)
    if row.category == "Processes":
        return "|".join(
            [
                row.category or "",
                row.name or "",
                row.executable_path or row.path or "",
                str(details.get("command", ""))[:120],
            ]
        )
    if row.category == "Network":
        return "|".join(
            [
                row.category or "",
                details.get("address", "") or row.network_ports or "",
                row.name or "",
            ]
        )
    return "|".join(
        [
            row.category or "",
            row.label or "",
            row.name or "",
            row.path or "",
            row.executable_path or "",
        ]
    )


def row_as_dict(row: InventoryItem) -> dict[str, Any]:
    details = json_loads(row.details_json)
    actions = json_loads(row.available_actions, default=[])
    return {
        "ID": row.id,
        "Stable ID": getattr(row, "stable_id", None),
        "Category": row.category,
        "Name": row.name,
        "Label": row.label,
        "Bundle ID": getattr(row, "bundle_id", None),
        "Type": row.item_type,
        "Subtype": getattr(row, "subtype", None),
        "Status": row.status,
        "Path": row.path,
        "Executable": row.executable_path,
        "Version": row.version,
        "Build": getattr(row, "build_number", None),
        "Publisher": row.publisher or row.vendor,
        "Signing": getattr(row, "signing_identity", None),
        "Team ID": getattr(row, "team_identifier", None),
        "Source": row.installation_source,
        "Running": row.running_state,
        "Startup": row.startup_state,
        "Enabled": getattr(row, "enabled_status", None),
        "CPU %": row.cpu,
        "Memory %": row.memory,
        "Disk": getattr(row, "disk_usage", None),
        "Ports": row.network_ports,
        "PID": getattr(row, "pid", None),
        "Parent": getattr(row, "parent_process", None),
        "Owner": getattr(row, "user_owner", None),
        "Risk": row.risk,
        "Classification": row.classification,
        "Confidence": getattr(row, "confidence", None),
        "Explanation": row.explanation,
        "Removal guidance": getattr(row, "removal_guidance", None),
        "Related": row.related_application,
        "Related package": getattr(row, "related_package", None),
        "Related service": getattr(row, "related_service", None),
        "Project": getattr(row, "project_key", None),
        "Startup impact": getattr(row, "startup_impact", None),
        "Knowledge": getattr(row, "knowledge_key", None),
        "Orphan": getattr(row, "orphan_status", False),
        "Protected": row.protected,
        "Actions": ", ".join(actions) if isinstance(actions, list) else str(actions or ""),
        "Details": details,
        "_row": row,
    }
