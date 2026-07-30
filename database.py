from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import DB_PATH, SCHEMA_VERSION, ensure_data_dirs, migrate_legacy_data


class Base(DeclarativeBase):
    pass


engine = create_engine(f"sqlite:///{DB_PATH}", future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

_INVENTORY_EXTRA_COLUMNS: dict[str, str] = {
    "label": "TEXT",
    "item_type": "TEXT",
    "executable_path": "TEXT",
    "publisher": "TEXT",
    "installation_source": "TEXT",
    "running_state": "TEXT",
    "startup_state": "TEXT",
    "network_ports": "TEXT",
    "classification": "TEXT",
    "explanation": "TEXT",
    "related_application": "TEXT",
    "available_actions": "TEXT",
    "stable_id": "TEXT",
    "technical_name": "TEXT",
    "subtype": "TEXT",
    "bundle_id": "TEXT",
    "signing_identity": "TEXT",
    "team_identifier": "TEXT",
    "configuration_path": "TEXT",
    "command": "TEXT",
    "user_owner": "TEXT",
    "group_owner": "TEXT",
    "enabled_status": "TEXT",
    "pid": "INTEGER",
    "parent_process": "TEXT",
    "disk_usage": "REAL",
    "install_date": "TEXT",
    "modification_date": "TEXT",
    "confidence": "REAL",
    "removal_guidance": "TEXT",
    "orphan_status": "INTEGER DEFAULT 0",
    "build_number": "TEXT",
    "related_package": "TEXT",
    "related_service": "TEXT",
    "project_key": "TEXT",
    "startup_impact": "TEXT",
    "knowledge_key": "TEXT",
    # V4 columns
    "workspace_id": "INTEGER",
    "usage_score": "REAL",
    "last_used_at": "TEXT",
}

_SNAPSHOT_EXTRA_COLUMNS: dict[str, str] = {
    "collector_errors": "TEXT",
    "name": "TEXT",
    "duration_seconds": "REAL",
}

_EVENT_EXTRA_COLUMNS: dict[str, str] = {
    "user": "TEXT",
    "target_type": "TEXT",
    "target_id": "TEXT",
    "target_path": "TEXT",
    "display_name": "TEXT",
    "requested_operation": "TEXT",
    "validation_result": "TEXT",
    "confirmation_result": "TEXT",
    "command_display": "TEXT",
    "exit_code": "INTEGER",
    "stdout": "TEXT",
    "stderr": "TEXT",
    "backup_path": "TEXT",
    "restore_available": "INTEGER DEFAULT 0",
}


def _existing_columns(table: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {row[1] for row in rows}


def _add_missing_columns(table: str, columns: dict[str, str]) -> None:
    existing = _existing_columns(table)
    if not existing:
        return
    with engine.begin() as conn:
        for name, typedef in columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {typedef}"))


def _set_schema_version(version: int) -> None:
    from datetime import datetime

    with engine.begin() as conn:
        row = conn.execute(text("SELECT id, version FROM schema_meta LIMIT 1")).fetchone()
        now = datetime.utcnow().isoformat(sep=" ")
        if row is None:
            conn.execute(
                text("INSERT INTO schema_meta (version, updated_at) VALUES (:v, :u)"),
                {"v": version, "u": now},
            )
        else:
            conn.execute(
                text("UPDATE schema_meta SET version = :v, updated_at = :u WHERE id = :id"),
                {"v": version, "u": now, "id": row[0]},
            )


def get_schema_version() -> int:
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version FROM schema_meta LIMIT 1")).fetchone()
            return int(row[0]) if row else 0
    except Exception:
        return 0


def init_db() -> None:
    """Create tables and apply additive schema migrations."""
    migrate_legacy_data()
    ensure_data_dirs()
    # Bind engine to current DB_PATH (tests may monkeypatch)
    global engine, SessionLocal
    engine = create_engine(f"sqlite:///{DB_PATH}", future=True)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    from models import (  # noqa: F401
        AutomationRule,
        AutomationRun,
        BackupRecord,
        Event,
        InventoryItem,
        RecommendationRecord,
        Relationship,
        SchemaMeta,
        Snapshot,
        TimelineEvent,
        UsageSample,
        UserAnnotation,
        Workspace,
        WorkspaceMember,
    )

    Base.metadata.bind = engine  # type: ignore[attr-defined]
    Base.metadata.create_all(bind=engine)
    _add_missing_columns("inventory_items", _INVENTORY_EXTRA_COLUMNS)
    _add_missing_columns("snapshots", _SNAPSHOT_EXTRA_COLUMNS)
    _add_missing_columns("events", _EVENT_EXTRA_COLUMNS)
    _set_schema_version(SCHEMA_VERSION)

    # Keep commonly imported SessionLocal aliases in sync when possible.
    for module_name in (
        "actions",
        "snapshot",
        "macscope.backup",
        "macscope.timeline",
        "macscope.annotations",
        "macscope.workspaces",
        "macscope.usage",
        "macscope.automation",
        "macscope.recommendations",
    ):
        try:
            mod = __import__(module_name, fromlist=["SessionLocal"])
            if hasattr(mod, "SessionLocal"):
                setattr(mod, "SessionLocal", SessionLocal)
        except Exception:
            pass
