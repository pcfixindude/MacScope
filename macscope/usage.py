from __future__ import annotations

"""Usage history tracking from snapshots (CPU/memory/disk/launch signals)."""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from database import SessionLocal
from inventory import Item
from models import UsageSample
from utils import json_dumps, logger


def record_usage_from_snapshot(snapshot_id: int, items: list[Item]) -> int:
    """Persist usage samples derived from the latest inventory snapshot."""
    samples: list[UsageSample] = []
    # System aggregate
    procs = [i for i in items if i.category == "Processes"]
    apps = [i for i in items if i.category == "Applications"]
    storage = [i for i in items if i.category == "Storage"]
    total_mem = sum(float(p.memory or 0) for p in procs)
    total_cpu = sum(float(p.cpu or 0) for p in procs)
    total_disk = sum(float(s.disk_usage or 0) for s in storage)
    samples.append(
        UsageSample(
            snapshot_id=snapshot_id,
            subject_type="system",
            subject_key="host",
            display_name="System",
            cpu=total_cpu,
            memory=total_mem,
            disk_usage=total_disk,
            launch_count=len([a for a in apps if a.running_state == "Running"]),
            details_json=json_dumps({"process_count": len(procs), "app_count": len(apps)}),
        )
    )

    # Top processes
    for proc in sorted(procs, key=lambda p: float(p.memory or 0), reverse=True)[:40]:
        samples.append(
            UsageSample(
                snapshot_id=snapshot_id,
                subject_type="process",
                subject_key=proc.stable_id or proc.name,
                display_name=proc.name,
                cpu=proc.cpu,
                memory=proc.memory,
                disk_usage=proc.disk_usage,
                details_json=json_dumps({"pid": proc.pid, "path": proc.path}),
            )
        )

    # Applications
    for app in apps:
        samples.append(
            UsageSample(
                snapshot_id=snapshot_id,
                subject_type="application",
                subject_key=app.stable_id or app.name,
                display_name=app.name,
                disk_usage=app.disk_usage,
                launch_count=1 if app.running_state == "Running" else 0,
                background_seconds=None,
                details_json=json_dumps({"running_state": app.running_state}),
            )
        )

    # Projects
    for project in [i for i in items if i.category == "Projects"]:
        samples.append(
            UsageSample(
                snapshot_id=snapshot_id,
                subject_type="project",
                subject_key=project.project_key or project.path or project.name,
                display_name=project.name,
                disk_usage=project.disk_usage,
                details_json=json_dumps({"git_status": project.status, "branch": project.version}),
            )
        )

    try:
        with SessionLocal() as db:
            db.add_all(samples)
            db.commit()
        return len(samples)
    except Exception as exc:
        logger.warning("Failed to record usage samples: %s", exc)
        return 0


def list_usage(
    *,
    subject_type: str | None = None,
    subject_key: str | None = None,
    days: int = 30,
    limit: int = 500,
) -> list[UsageSample]:
    since = datetime.utcnow() - timedelta(days=max(1, days))
    with SessionLocal() as db:
        q = db.query(UsageSample).filter(UsageSample.created_at >= since).order_by(UsageSample.id.desc())
        if subject_type:
            q = q.filter(UsageSample.subject_type == subject_type)
        if subject_key:
            q = q.filter(UsageSample.subject_key == subject_key)
        return q.limit(limit).all()


def usage_series(subject_type: str = "system", subject_key: str = "host", days: int = 30) -> list[dict[str, Any]]:
    rows = list(reversed(list_usage(subject_type=subject_type, subject_key=subject_key, days=days, limit=400)))
    return [
        {
            "created_at": r.created_at,
            "cpu": r.cpu,
            "memory": r.memory,
            "disk_usage": r.disk_usage,
            "launch_count": r.launch_count,
            "display_name": r.display_name,
        }
        for r in rows
    ]


def detect_anomalies(days: int = 14) -> list[dict[str, Any]]:
    """Highlight unusual jumps in system memory/disk relative to recent average."""
    series = usage_series("system", "host", days=days)
    if len(series) < 4:
        return []
    anomalies = []
    mem_vals = [float(p["memory"] or 0) for p in series]
    disk_vals = [float(p["disk_usage"] or 0) for p in series]
    avg_mem = sum(mem_vals[:-1]) / max(len(mem_vals) - 1, 1)
    avg_disk = sum(disk_vals[:-1]) / max(len(disk_vals) - 1, 1)
    latest = series[-1]
    if avg_mem and float(latest["memory"] or 0) > avg_mem * 1.5:
        anomalies.append(
            {
                "kind": "memory_spike",
                "message": f"System memory sum {latest['memory']:.1f} is >1.5× recent average {avg_mem:.1f}.",
                "created_at": latest["created_at"],
            }
        )
    if avg_disk and float(latest["disk_usage"] or 0) > avg_disk + (2 * 1024**3):
        anomalies.append(
            {
                "kind": "disk_growth",
                "message": "Observed storage summary grew by more than ~2 GB versus recent average.",
                "created_at": latest["created_at"],
            }
        )
    return anomalies


def application_launch_frequency(days: int = 30) -> list[dict[str, Any]]:
    rows = list_usage(subject_type="application", days=days, limit=2000)
    counts: dict[str, int] = defaultdict(int)
    sizes: dict[str, float] = {}
    for row in rows:
        counts[row.display_name] += int(row.launch_count or 0)
        if row.disk_usage:
            sizes[row.display_name] = float(row.disk_usage)
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return [
        {"name": name, "launch_observations": count, "disk_usage": sizes.get(name)}
        for name, count in ranked[:40]
    ]
