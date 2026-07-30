from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _temp_database(tmp_path, monkeypatch):
    """Point MacScope persistence at temporary paths for every test."""
    data_root = tmp_path / "MacScopeData"
    db_path = data_root / "database" / "test_macscope.db"
    backups = data_root / "backups"
    settings_path = data_root / "settings.json"
    for path in (
        db_path.parent,
        backups,
        data_root / "logs",
        data_root / "reports",
        data_root / "exports",
        data_root / "cache",
        data_root / "disabled-items",
    ):
        path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("config.DATA_ROOT", data_root)
    monkeypatch.setattr("config.DB_PATH", db_path)
    monkeypatch.setattr("config.BACKUPS_DIR", backups)
    monkeypatch.setattr("config.SETTINGS_PATH", settings_path)
    monkeypatch.setattr("macscope.settings.SETTINGS_PATH", settings_path)
    monkeypatch.setattr("config.LOG_PATH", data_root / "logs" / "macscope.log")
    monkeypatch.setattr("database.DB_PATH", db_path)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import database
    from macscope.settings import Settings, save_settings

    database.engine = create_engine(f"sqlite:///{db_path}", future=True)
    database.SessionLocal = sessionmaker(bind=database.engine, expire_on_commit=False)
    monkeypatch.setattr("actions.SessionLocal", database.SessionLocal)
    monkeypatch.setattr("snapshot.SessionLocal", database.SessionLocal)
    monkeypatch.setattr("macscope.backup.SessionLocal", database.SessionLocal)
    monkeypatch.setattr("actions.BACKUPS_DIR", backups)
    monkeypatch.setattr("macscope.backup.BACKUPS_DIR", backups)
    monkeypatch.setattr("macscope.backup.DISABLED_ITEMS_DIR", data_root / "disabled-items")
    database.init_db()
    from models import (  # noqa: F401
        BackupRecord,
        Event,
        InventoryItem,
        Relationship,
        SchemaMeta,
        Snapshot,
    )

    database.Base.metadata.create_all(database.engine)

    settings = Settings(
        enable_destructive_actions=True,
        safety_notice_acknowledged=True,
        require_typed_confirmation=False,
    )
    save_settings(settings)
    yield
