from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from models import InventoryItem
from snapshot import row_as_dict, row_identity_key


@dataclass
class ComparisonResult:
    added: list[dict[str, Any]] = field(default_factory=list)
    removed: list[dict[str, Any]] = field(default_factory=list)
    changed: list[dict[str, Any]] = field(default_factory=list)
    newly_running: list[dict[str, Any]] = field(default_factory=list)
    newly_enabled_startup: list[dict[str, Any]] = field(default_factory=list)
    newly_opened_ports: list[dict[str, Any]] = field(default_factory=list)
    closed_ports: list[dict[str, Any]] = field(default_factory=list)
    version_changes: list[dict[str, Any]] = field(default_factory=list)
    service_status_changes: list[dict[str, Any]] = field(default_factory=list)
    new_applications: list[dict[str, Any]] = field(default_factory=list)
    removed_applications: list[dict[str, Any]] = field(default_factory=list)
    new_ai_models: list[dict[str, Any]] = field(default_factory=list)
    removed_ai_models: list[dict[str, Any]] = field(default_factory=list)
    storage_changes: list[dict[str, Any]] = field(default_factory=list)
    security_changes: list[dict[str, Any]] = field(default_factory=list)
    running_state_changes: list[dict[str, Any]] = field(default_factory=list)
    startup_state_changes: list[dict[str, Any]] = field(default_factory=list)


_COMPARE_FIELDS = (
    "status",
    "version",
    "running_state",
    "startup_state",
    "risk",
    "classification",
    "path",
    "executable_path",
    "network_ports",
    "vendor",
    "publisher",
    "disk_usage",
    "enabled_status",
)


def compare_snapshots(
    older: list[InventoryItem],
    newer: list[InventoryItem],
) -> ComparisonResult:
    result = ComparisonResult()
    older_map = {row_identity_key(row): row for row in older}
    newer_map = {row_identity_key(row): row for row in newer}
    older_keys = set(older_map)
    newer_keys = set(newer_map)

    for key in sorted(newer_keys - older_keys):
        row = newer_map[key]
        entry = row_as_dict(row)
        result.added.append(entry)
        if row.category == "Applications":
            result.new_applications.append(entry)
        if row.category == "AI":
            result.new_ai_models.append(entry)
        if row.category == "Processes" and (row.running_state == "Running" or row.status == "Running"):
            result.newly_running.append(entry)
        if row.category in {"Startup", "Login Items", "Background Items"}:
            result.newly_enabled_startup.append(entry)
        if row.category == "Network":
            result.newly_opened_ports.append(entry)

    for key in sorted(older_keys - newer_keys):
        row = older_map[key]
        entry = row_as_dict(row)
        result.removed.append(entry)
        if row.category == "Applications":
            result.removed_applications.append(entry)
        if row.category == "AI":
            result.removed_ai_models.append(entry)
        if row.category == "Network":
            result.closed_ports.append(entry)

    for key in sorted(older_keys & newer_keys):
        before = older_map[key]
        after = newer_map[key]
        changes: dict[str, tuple[Any, Any]] = {}
        for field_name in _COMPARE_FIELDS:
            left = getattr(before, field_name, None)
            right = getattr(after, field_name, None)
            if left != right:
                changes[field_name] = (left, right)
        if not changes:
            continue
        entry = {
            **row_as_dict(after),
            "changes": {k: {"from": v[0], "to": v[1]} for k, v in changes.items()},
        }
        result.changed.append(entry)
        if "version" in changes:
            result.version_changes.append(entry)
        if before.category == "Services" and ("status" in changes or "running_state" in changes):
            result.service_status_changes.append(entry)
        if "running_state" in changes:
            result.running_state_changes.append(entry)
            old_r, new_r = changes["running_state"]
            if new_r == "Running" and old_r != "Running":
                result.newly_running.append(entry)
        if "startup_state" in changes or "enabled_status" in changes:
            result.startup_state_changes.append(entry)
        if before.category == "Storage" and "disk_usage" in changes:
            result.storage_changes.append(entry)
        if before.category == "Security" and "status" in changes:
            result.security_changes.append(entry)
        if before.category == "Network" and "network_ports" in changes:
            result.newly_opened_ports.append(entry)
    return result
