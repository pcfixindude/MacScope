from __future__ import annotations

from datetime import datetime

from database import SessionLocal
from models import UserAnnotation


def upsert_annotation(stable_id: str, kind: str, value: str = "", display_name: str | None = None) -> UserAnnotation:
    with SessionLocal() as db:
        row = (
            db.query(UserAnnotation)
            .filter_by(stable_id=stable_id, kind=kind)
            .order_by(UserAnnotation.id.desc())
            .first()
        )
        if row is None:
            row = UserAnnotation(
                stable_id=stable_id,
                kind=kind,
                value=value,
                display_name=display_name,
            )
            db.add(row)
        else:
            row.value = value
            row.display_name = display_name or row.display_name
            row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return row


def remove_annotation(stable_id: str, kind: str) -> None:
    with SessionLocal() as db:
        db.query(UserAnnotation).filter_by(stable_id=stable_id, kind=kind).delete()
        db.commit()


def list_annotations(kind: str | None = None) -> list[UserAnnotation]:
    with SessionLocal() as db:
        q = db.query(UserAnnotation).order_by(UserAnnotation.updated_at.desc())
        if kind:
            q = q.filter(UserAnnotation.kind == kind)
        return q.all()


def is_favorited(stable_id: str) -> bool:
    with SessionLocal() as db:
        return (
            db.query(UserAnnotation).filter_by(stable_id=stable_id, kind="favorite").first()
            is not None
        )


def is_pinned(stable_id: str) -> bool:
    with SessionLocal() as db:
        return db.query(UserAnnotation).filter_by(stable_id=stable_id, kind="pin").first() is not None


def get_note(stable_id: str) -> str:
    with SessionLocal() as db:
        row = db.query(UserAnnotation).filter_by(stable_id=stable_id, kind="note").first()
        return row.value if row else ""
