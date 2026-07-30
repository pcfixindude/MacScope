from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from macscope.stable_id import item_stable_id


@dataclass
class Item:
    """Unified inventory item produced by collectors."""

    category: str
    name: str
    path: str | None = None
    status: str | None = None
    vendor: str | None = None
    version: str | None = None
    cpu: float | None = None
    memory: float | None = None
    risk: str = "Unknown"
    protected: bool = False
    details: dict[str, Any] = field(default_factory=dict)
    label: str | None = None
    item_type: str | None = None
    executable_path: str | None = None
    publisher: str | None = None
    installation_source: str | None = None
    running_state: str | None = None
    startup_state: str | None = None
    network_ports: str | None = None
    classification: str | None = None
    explanation: str | None = None
    related_application: str | None = None
    available_actions: list[str] = field(default_factory=list)
    # V2 unified fields
    stable_id: str | None = None
    technical_name: str | None = None
    subtype: str | None = None
    bundle_id: str | None = None
    signing_identity: str | None = None
    team_identifier: str | None = None
    configuration_path: str | None = None
    command: str | None = None
    user_owner: str | None = None
    group_owner: str | None = None
    enabled_status: str | None = None
    pid: int | None = None
    parent_process: str | None = None
    disk_usage: float | None = None
    install_date: str | None = None
    modification_date: str | None = None
    last_observed: str | None = None
    first_observed: str | None = None
    related_package: str | None = None
    related_service: str | None = None
    confidence: float | None = None
    removal_guidance: str | None = None
    orphan_status: bool = False
    build_number: str | None = None

    def ensure_stable_id(self) -> str:
        if self.stable_id:
            return self.stable_id
        self.stable_id = item_stable_id(
            category=self.category,
            name=self.name,
            path=self.path,
            label=self.label or self.bundle_id,
            bundle_id=self.bundle_id,
            executable_path=self.executable_path,
            extra=str(self.pid) if self.category == "Processes" and self.pid else (
                self.network_ports if self.category == "Network" else None
            ),
        )
        return self.stable_id

    def identity_key(self) -> str:
        self.ensure_stable_id()
        return self.stable_id or ""
