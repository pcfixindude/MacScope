from __future__ import annotations

"""Workspace Manager — complete development environments with graceful start/stop."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from database import SessionLocal
from models import Workspace, WorkspaceMember
from utils import json_dumps, json_loads, logger, run_command


MEMBER_TYPES = (
    "application",
    "project",
    "url",
    "terminal",
    "venv",
    "docker",
    "brew_service",
    "port",
    "ai_server",
    "startup_script",
)


@dataclass
class WorkspaceStatus:
    workspace_id: int
    name: str
    status: str
    health: str
    members: int
    running_members: int
    messages: list[str]


def list_workspaces() -> list[Workspace]:
    with SessionLocal() as db:
        return db.query(Workspace).order_by(Workspace.pinned.desc(), Workspace.name.asc()).all()


def get_workspace(workspace_id: int) -> Workspace | None:
    with SessionLocal() as db:
        return db.query(Workspace).filter_by(id=workspace_id).first()


def list_members(workspace_id: int) -> list[WorkspaceMember]:
    with SessionLocal() as db:
        return (
            db.query(WorkspaceMember)
            .filter_by(workspace_id=workspace_id)
            .order_by(WorkspaceMember.sort_order.asc(), WorkspaceMember.id.asc())
            .all()
        )


def create_workspace(name: str, description: str = "", *, pinned: bool = False) -> Workspace:
    with SessionLocal() as db:
        ws = Workspace(name=name.strip() or "Workspace", description=description, pinned=pinned)
        db.add(ws)
        db.commit()
        db.refresh(ws)
        return ws


def update_workspace(workspace_id: int, **fields: Any) -> Workspace | None:
    with SessionLocal() as db:
        ws = db.query(Workspace).filter_by(id=workspace_id).first()
        if not ws:
            return None
        for key, value in fields.items():
            if hasattr(ws, key) and key not in {"id", "created_at"}:
                setattr(ws, key, value)
        ws.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(ws)
        return ws


def delete_workspace(workspace_id: int) -> None:
    with SessionLocal() as db:
        db.query(WorkspaceMember).filter_by(workspace_id=workspace_id).delete()
        db.query(Workspace).filter_by(id=workspace_id).delete()
        db.commit()


def add_member(
    workspace_id: int,
    member_type: str,
    label: str,
    value: str,
    *,
    stable_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> WorkspaceMember:
    if member_type not in MEMBER_TYPES:
        raise ValueError(f"Unsupported member_type: {member_type}")
    with SessionLocal() as db:
        member = WorkspaceMember(
            workspace_id=workspace_id,
            member_type=member_type,
            label=label,
            value=value,
            stable_id=stable_id,
            details_json=json_dumps(details or {}),
        )
        db.add(member)
        db.commit()
        db.refresh(member)
        return member


def remove_member(member_id: int) -> None:
    with SessionLocal() as db:
        db.query(WorkspaceMember).filter_by(id=member_id).delete()
        db.commit()


def workspace_status(workspace_id: int, inventory_rows: list[Any] | None = None) -> WorkspaceStatus:
    ws = get_workspace(workspace_id)
    if not ws:
        return WorkspaceStatus(workspace_id, "?", "missing", "unknown", 0, 0, ["Workspace not found"])
    members = list_members(workspace_id)
    messages: list[str] = []
    running = 0
    by_stable = {getattr(r, "stable_id", None): r for r in (inventory_rows or []) if getattr(r, "stable_id", None)}
    for member in members:
        if member.member_type in {"docker", "brew_service", "application", "ai_server", "port"}:
            row = by_stable.get(member.stable_id)
            if row is not None:
                state = (getattr(row, "running_state", None) or getattr(row, "status", "") or "").lower()
                if state in {"running", "active", "started"}:
                    running += 1
                else:
                    messages.append(f"{member.label or member.value}: {state or 'not observed running'}")
            else:
                messages.append(f"{member.label or member.value}: not in current snapshot")
    health = "healthy" if members and running == len([m for m in members if m.member_type in {"docker", "brew_service", "application", "ai_server"}]) else (
        "degraded" if running else "stopped"
    )
    if not members:
        health = "empty"
    return WorkspaceStatus(ws.id, ws.name, ws.status, health, len(members), running, messages)


def start_workspace(workspace_id: int) -> list[str]:
    """Gracefully start only assigned workspace members."""
    members = list_members(workspace_id)
    logs: list[str] = []
    for member in members:
        try:
            if member.member_type == "application" and member.value.endswith(".app"):
                run_command(["open", member.value], timeout=20)
                logs.append(f"Opened application: {member.label or member.value}")
            elif member.member_type == "url" and member.value.startswith(("http://", "https://")):
                run_command(["open", member.value], timeout=20)
                logs.append(f"Opened URL: {member.value}")
            elif member.member_type == "project" and member.value:
                run_command(["open", member.value], timeout=20)
                logs.append(f"Opened project folder: {member.value}")
            elif member.member_type == "brew_service" and member.value:
                run_command(["brew", "services", "start", member.value], timeout=60)
                logs.append(f"Started brew service: {member.value}")
            elif member.member_type == "docker" and member.value:
                run_command(["docker", "start", member.value], timeout=60)
                logs.append(f"Started container: {member.value}")
            elif member.member_type == "ai_server" and member.value:
                # Prefer opening app bundle / URL; do not invent server binaries
                run_command(["open", member.value], timeout=20)
                logs.append(f"Opened AI server target: {member.value}")
            elif member.member_type == "startup_script" and member.value:
                run_command(["/bin/zsh", "-lc", member.value], timeout=120)
                logs.append(f"Ran startup script for {member.label or 'script'}")
            elif member.member_type == "terminal" and member.value:
                run_command(
                    ["osascript", "-e", f'tell application "Terminal" to do script "{member.value.replace(chr(34), chr(92)+chr(34))}"'],
                    timeout=20,
                )
                logs.append(f"Launched terminal command: {member.label or member.value[:40]}")
            elif member.member_type in {"venv", "port"}:
                logs.append(f"Noted {member.member_type}: {member.label or member.value} (no process start required)")
            else:
                logs.append(f"Skipped unsupported/empty member: {member.member_type}")
        except Exception as exc:
            logger.warning("Workspace start member failed: %s", exc)
            logs.append(f"Failed {member.label or member.value}: {exc}")
    update_workspace(workspace_id, status="running", health="starting")
    return logs


def stop_workspace(workspace_id: int) -> list[str]:
    """Gracefully stop only assigned members — never unrelated software."""
    members = list_members(workspace_id)
    logs: list[str] = []
    # Stop in reverse order for dependency friendliness
    for member in reversed(members):
        try:
            if member.member_type == "docker" and member.value:
                run_command(["docker", "stop", member.value], timeout=90)
                logs.append(f"Stopped container: {member.value}")
            elif member.member_type == "brew_service" and member.value:
                run_command(["brew", "services", "stop", member.value], timeout=60)
                logs.append(f"Stopped brew service: {member.value}")
            elif member.member_type == "application" and member.value.endswith(".app"):
                app_name = member.value.rstrip("/").split("/")[-1].removesuffix(".app")
                run_command(["osascript", "-e", f'quit app "{app_name}"'], timeout=30)
                logs.append(f"Quit application: {app_name}")
            elif member.member_type == "startup_script":
                details = json_loads(member.details_json)
                stop_cmd = details.get("stop_command")
                if stop_cmd:
                    run_command(["/bin/zsh", "-lc", str(stop_cmd)], timeout=120)
                    logs.append(f"Ran stop script for {member.label or 'script'}")
                else:
                    logs.append(f"No stop_command configured for {member.label or 'script'}")
            else:
                logs.append(f"Left alone (no stop action): {member.member_type} {member.label or member.value}")
        except Exception as exc:
            logger.warning("Workspace stop member failed: %s", exc)
            logs.append(f"Failed stop {member.label or member.value}: {exc}")
    update_workspace(workspace_id, status="stopped", health="stopped")
    return logs


def restart_workspace(workspace_id: int) -> list[str]:
    logs = stop_workspace(workspace_id)
    logs.extend(start_workspace(workspace_id))
    update_workspace(workspace_id, status="running", health="restarted")
    return logs
