from __future__ import annotations

"""Local automation rules — snapshots, reports, threshold notifications."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from database import SessionLocal
from macscope.settings import load_settings
from macscope.timeline import list_timeline, record_timeline
from models import AutomationRule, AutomationRun
from utils import format_bytes, json_dumps, json_loads, logger


DEFAULT_RULES = [
    ("Weekly snapshots", "weekly_snapshot", "weekly", {}),
    ("Monthly reports", "monthly_report", "monthly", {}),
    ("Notify startup changes", "notify_startup_change", "on_snapshot", {}),
    ("Notify new ports", "notify_new_ports", "on_snapshot", {}),
    ("Notify Downloads threshold", "notify_downloads", "on_snapshot", {}),
    ("Notify rapid storage growth", "notify_storage_growth", "on_snapshot", {}),
]


def ensure_default_rules() -> None:
    with SessionLocal() as db:
        existing = {r.rule_type for r in db.query(AutomationRule).all()}
        for name, rule_type, schedule, config in DEFAULT_RULES:
            if rule_type in existing:
                continue
            db.add(
                AutomationRule(
                    name=name,
                    rule_type=rule_type,
                    schedule=schedule,
                    config_json=json_dumps(config),
                    enabled=True,
                )
            )
        db.commit()


def list_rules() -> list[AutomationRule]:
    ensure_default_rules()
    with SessionLocal() as db:
        return db.query(AutomationRule).order_by(AutomationRule.id.asc()).all()


def set_rule_enabled(rule_id: int, enabled: bool) -> None:
    with SessionLocal() as db:
        rule = db.query(AutomationRule).filter_by(id=rule_id).first()
        if rule:
            rule.enabled = enabled
            rule.updated_at = datetime.utcnow()
            db.commit()


def list_runs(limit: int = 50) -> list[AutomationRun]:
    with SessionLocal() as db:
        return db.query(AutomationRun).order_by(AutomationRun.id.desc()).limit(limit).all()


def _log_run(rule: AutomationRule, result: str, message: str, details: dict[str, Any] | None = None) -> None:
    with SessionLocal() as db:
        db.add(
            AutomationRun(
                rule_id=rule.id,
                rule_name=rule.name,
                result=result,
                message=message,
                details_json=json_dumps(details or {}),
            )
        )
        row = db.query(AutomationRule).filter_by(id=rule.id).first()
        if row:
            row.last_run_at = datetime.utcnow()
            row.last_result = message[:1000]
        db.commit()
    record_timeline(
        "automation",
        f"Automation: {rule.name}",
        summary=message,
        source="system",
        details={"result": result, **(details or {})},
    )


def run_rule(rule: AutomationRule, *, inventory_rows: list[Any] | None = None, force: bool = False) -> str:
    settings = load_settings()
    if not settings.enable_automation and not force:
        return "Automation disabled in Settings"
    try:
        if rule.rule_type == "weekly_snapshot":
            msg = "Weekly snapshot rule armed — use Collect snapshot / scheduler to create snapshots."
            _log_run(rule, "ok", msg)
            return msg
        if rule.rule_type == "monthly_report":
            msg = "Monthly report rule armed — generate from Reports page or run_due_rules after snapshot."
            _log_run(rule, "ok", msg)
            return msg
        if rule.rule_type == "notify_startup_change":
            events = [e for e in list_timeline(limit=50, event_type="startup_changed")]
            msg = f"{len(events)} recent startup change event(s) in timeline."
            _log_run(rule, "notify" if events else "ok", msg, {"count": len(events)})
            return msg
        if rule.rule_type == "notify_new_ports":
            events = [e for e in list_timeline(limit=50, event_type="network_changed")]
            msg = f"{len(events)} recent network listener change event(s)."
            _log_run(rule, "notify" if events else "ok", msg, {"count": len(events)})
            return msg
        if rule.rule_type == "notify_downloads":
            downloads = Path.home() / "Downloads"
            total = 0
            if downloads.exists():
                for child in downloads.iterdir():
                    try:
                        if child.is_file():
                            total += child.stat().st_size
                    except OSError:
                        continue
            threshold = float(settings.downloads_notify_gb) * 1024**3
            over = total >= threshold
            msg = f"Downloads size ≈ {format_bytes(total)} (threshold {settings.downloads_notify_gb} GB)."
            _log_run(rule, "notify" if over else "ok", msg, {"bytes": total})
            return msg
        if rule.rule_type == "notify_storage_growth":
            from macscope.usage import detect_anomalies

            anomalies = [a for a in detect_anomalies() if a.get("kind") == "disk_growth"]
            msg = anomalies[0]["message"] if anomalies else "No rapid storage growth anomaly detected."
            _log_run(rule, "notify" if anomalies else "ok", msg)
            return msg
        msg = f"Unknown rule type: {rule.rule_type}"
        _log_run(rule, "error", msg)
        return msg
    except Exception as exc:
        logger.warning("Automation rule failed: %s", exc)
        _log_run(rule, "error", str(exc))
        return str(exc)


def run_due_rules(*, inventory_rows: list[Any] | None = None) -> list[str]:
    """Run enabled on_snapshot / due schedule rules. Local only."""
    settings = load_settings()
    if not settings.enable_automation:
        return ["Automation disabled"]
    messages = []
    now = datetime.utcnow()
    for rule in list_rules():
        if not rule.enabled:
            continue
        due = False
        if rule.schedule == "on_snapshot":
            due = True
        elif rule.schedule == "weekly":
            due = rule.last_run_at is None or (now - rule.last_run_at) >= timedelta(days=7)
        elif rule.schedule == "monthly":
            due = rule.last_run_at is None or (now - rule.last_run_at) >= timedelta(days=28)
        elif rule.schedule == "manual":
            due = False
        if due:
            messages.append(run_rule(rule, inventory_rows=inventory_rows))
    return messages
