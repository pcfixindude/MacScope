from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class SchemaMeta(Base):
    __tablename__ = "schema_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(Integer, index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    path: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    vendor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    version: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    cpu: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    memory: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk: Mapped[str] = mapped_column(String(32), default="Unknown", index=True)
    protected: Mapped[bool] = mapped_column(Boolean, default=False)
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    item_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    executable_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    publisher: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    installation_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    running_state: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    startup_state: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    network_ports: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    classification: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    related_application: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    available_actions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # V2 columns
    stable_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    technical_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subtype: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    bundle_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    signing_identity: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    team_identifier: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    configuration_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    command: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_owner: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    group_owner: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    enabled_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    pid: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    parent_process: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    disk_usage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    install_date: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    modification_date: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    removal_guidance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    orphan_status: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    build_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    related_package: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    related_service: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # V3 columns
    project_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    startup_impact: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    knowledge_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    hostname: Mapped[str] = mapped_column(String(255), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    collector_errors: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    action: Mapped[str] = mapped_column(String(128), index=True)
    target: Mapped[str] = mapped_column(Text)
    result: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text, default="")
    user: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    target_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    target_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    requested_operation: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    validation_result: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    confirmation_result: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    command_display: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exit_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stdout: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stderr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    backup_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    restore_available: Mapped[bool] = mapped_column(Boolean, default=False)


class Relationship(Base):
    __tablename__ = "relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(Integer, index=True)
    source_stable_id: Mapped[str] = mapped_column(String(128), index=True)
    target_stable_id: Mapped[str] = mapped_column(String(128), index=True)
    relation_type: Mapped[str] = mapped_column(String(128), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class BackupRecord(Base):
    __tablename__ = "backups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    kind: Mapped[str] = mapped_column(String(64), index=True)
    source_path: Mapped[str] = mapped_column(Text)
    backup_path: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    restorable: Mapped[bool] = mapped_column(Boolean, default=True)


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(512))
    summary: Mapped[str] = mapped_column(Text, default="")
    stable_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    snapshot_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(64), default="system")  # system | action | snapshot
    details_json: Mapped[str] = mapped_column(Text, default="{}")


class UserAnnotation(Base):
    """Favorites, pins, and notes for inventory items (stable_id keyed)."""

    __tablename__ = "user_annotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    stable_id: Mapped[str] = mapped_column(String(128), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)  # favorite | pin | note
    value: Mapped[str] = mapped_column(Text, default="")
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
