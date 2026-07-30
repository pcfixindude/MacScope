from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from config import (
    ALLOW_DESTRUCTIVE_ACTIONS,
    DEFAULT_AI_ROOTS,
    DEFAULT_PROJECT_ROOTS,
    SETTINGS_PATH,
    ensure_data_dirs,
)


@dataclass
class Settings:
    theme: str = "system"
    show_apple_items: bool = True
    show_protected_items: bool = True
    show_advanced_details: bool = True
    enable_destructive_actions: bool = False
    enable_administrator_actions: bool = False
    require_typed_confirmation: bool = True
    safety_notice_acknowledged: bool = False
    snapshot_retention: int = 50
    automatic_snapshot_on_startup: bool = False
    project_scan_roots: list[str] = field(default_factory=lambda: list(DEFAULT_PROJECT_ROOTS))
    ai_scan_roots: list[str] = field(default_factory=lambda: list(DEFAULT_AI_ROOTS))
    scan_depth: int = 4
    cache_duration_seconds: int = 300
    redact_username: bool = True
    redact_home_path: bool = True
    redact_command_args: bool = True
    redact_local_ips: bool = False
    redact_hostname: bool = True
    report_output_folder: str = ""
    prefer_trash: bool = True
    collectors_enabled: dict[str, bool] = field(
        default_factory=lambda: {
            "Applications": True,
            "Processes": True,
            "Startup": True,
            "Login Items": True,
            "Homebrew": True,
            "Network": True,
            "System": True,
            "Python": True,
            "Node": True,
            "Docker": True,
            "AI": True,
            "Storage": True,
            "Security": True,
            "Crashes": True,
            "Permissions": True,
        }
    )
    collect_network_listeners: bool = True
    collect_docker: bool = True
    collect_ai_models: bool = True
    # V4 settings
    custom_project_roots: list[str] = field(default_factory=list)
    pinned_project_keys: list[str] = field(default_factory=list)
    enable_usage_tracking: bool = True
    enable_automation: bool = True
    downloads_notify_gb: float = 20.0
    storage_growth_notify_gb: float = 5.0
    collector_cache_seconds: int = 120

    def destructive_allowed(self) -> bool:
        return bool(self.enable_destructive_actions and self.safety_notice_acknowledged)

    def all_project_roots(self) -> list[str]:
        roots: list[str] = []
        for root in list(self.project_scan_roots) + list(self.custom_project_roots):
            if root and root not in roots:
                roots.append(root)
        return roots


_DEFAULT = Settings()


def _defaults_dict() -> dict[str, Any]:
    return asdict(_DEFAULT)


def load_settings() -> Settings:
    ensure_data_dirs()
    raw: dict[str, Any] = {}
    if SETTINGS_PATH.exists():
        try:
            raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
    data = _defaults_dict()
    data.update({k: v for k, v in raw.items() if k in data})
    # Nested dict merge for collectors_enabled
    if isinstance(raw.get("collectors_enabled"), dict):
        merged = data["collectors_enabled"]
        merged.update(raw["collectors_enabled"])
        data["collectors_enabled"] = merged
    if not data.get("report_output_folder"):
        from config import REPORTS_DIR

        data["report_output_folder"] = str(REPORTS_DIR)
    return Settings(**data)


def save_settings(settings: Settings) -> None:
    ensure_data_dirs()
    SETTINGS_PATH.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")


def update_settings(**kwargs: Any) -> Settings:
    settings = load_settings()
    for key, value in kwargs.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    save_settings(settings)
    return settings
