from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from config import BACKUPS_DIR, DISABLED_ITEMS_DIR, ensure_data_dirs
from database import SessionLocal
from models import BackupRecord
from protection import is_protected_path
from utils import json_dumps, logger


def create_file_backup(source: str | Path, *, kind: str = "plist", metadata: dict[str, Any] | None = None) -> Path:
    """Copy a file into MacScope backups and record metadata."""
    ensure_data_dirs()
    src = Path(source).expanduser().resolve()
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"Backup source missing: {src}")
    if is_protected_path(str(src)):
        raise PermissionError("Refusing to back up protected system path.")
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dest_dir = BACKUPS_DIR / kind
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{src.name}.{stamp}.bak"
    shutil.copy2(src, dest)
    with SessionLocal() as db:
        db.add(
            BackupRecord(
                kind=kind,
                source_path=str(src),
                backup_path=str(dest),
                metadata_json=json_dumps(metadata or {}),
                restorable=True,
            )
        )
        db.commit()
    logger.info("Backup created %s -> %s", src, dest)
    return dest


def restore_file_backup(backup_path: str | Path) -> Path:
    ensure_data_dirs()
    backup = Path(backup_path).expanduser().resolve()
    if not backup.exists():
        raise FileNotFoundError(str(backup))
    with SessionLocal() as db:
        record = db.query(BackupRecord).filter_by(backup_path=str(backup)).first()
        if record is None:
            # Infer source from metadata filename pattern name.stamp.bak
            raise FileNotFoundError("No backup record found for this path.")
        target = Path(record.source_path)
        if is_protected_path(str(target)):
            raise PermissionError("Refusing to restore onto protected path.")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, target)
        record.restorable = True
        db.commit()
        return target


def move_to_disabled_items(path: str | Path) -> Path:
    ensure_data_dirs()
    src = Path(path).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(str(src))
    if is_protected_path(str(src)):
        raise PermissionError("Protected path.")
    dest = DISABLED_ITEMS_DIR / src.name
    if dest.exists():
        stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        dest = DISABLED_ITEMS_DIR / f"{src.stem}.{stamp}{src.suffix}"
    create_file_backup(src, kind="disabled-items")
    shutil.move(str(src), str(dest))
    return dest


def list_backups(limit: int = 200) -> list[BackupRecord]:
    with SessionLocal() as db:
        return db.query(BackupRecord).order_by(BackupRecord.id.desc()).limit(limit).all()
