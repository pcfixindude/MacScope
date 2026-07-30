from __future__ import annotations

import json
import os
from pathlib import Path

APP_NAME = "MacScope"
APP_VERSION = "3.0.0"

# Source / install directory (repository root)
BASE_DIR = Path(__file__).resolve().parent
VERSION_PATH = BASE_DIR / "VERSION"

# Runtime data lives outside the repository
DATA_ROOT = Path.home() / "Library" / "Application Support" / APP_NAME
DATABASE_DIR = DATA_ROOT / "database"
BACKUPS_DIR = DATA_ROOT / "backups"
REPORTS_DIR = DATA_ROOT / "reports"
LOGS_DIR = DATA_ROOT / "logs"
EXPORTS_DIR = DATA_ROOT / "exports"
CACHE_DIR = DATA_ROOT / "cache"
DISABLED_ITEMS_DIR = DATA_ROOT / "disabled-items"
SETTINGS_PATH = DATA_ROOT / "settings.json"
DB_PATH = DATABASE_DIR / "macscope.db"
LOG_PATH = LOGS_DIR / "macscope.log"
SCHEMA_VERSION = 3

# Legacy repo-local paths (migrated on first launch if present)
LEGACY_DB_PATH = BASE_DIR / "macscope.db"
LEGACY_LOG_PATH = BASE_DIR / "macscope.log"

PROTECTED_PROCESS_NAMES = frozenset(
    {
        "launchd",
        "WindowServer",
        "loginwindow",
        "kernel_task",
        "kernelmanagerd",
        "sysmond",
        "opendirectoryd",
        "Finder",
        "SystemUIServer",
        "Dock",
    }
)

DEFAULT_PROJECT_ROOTS = [
    str(Path.home() / "Projects"),
    str(Path.home() / "Developer"),
    str(Path.home() / "Documents"),
]

DEFAULT_AI_ROOTS = [
    str(Path.home() / ".cache" / "huggingface"),
    str(Path.home() / ".ollama"),
    str(Path.home() / ".lmstudio"),
    str(Path.home() / "Library" / "Application Support" / "LM Studio"),
    str(Path.home() / "Models"),
    str(Path.home() / "AI"),
]

# Destructive actions remain gated until Settings acknowledgement.
ALLOW_DESTRUCTIVE_ACTIONS = False


def ensure_data_dirs() -> None:
    for path in (
        DATA_ROOT,
        DATABASE_DIR,
        BACKUPS_DIR,
        REPORTS_DIR,
        LOGS_DIR,
        EXPORTS_DIR,
        CACHE_DIR,
        DISABLED_ITEMS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def migrate_legacy_data() -> None:
    """Copy legacy repo-local database into Application Support once."""
    ensure_data_dirs()
    if LEGACY_DB_PATH.exists() and not DB_PATH.exists():
        import shutil

        shutil.copy2(LEGACY_DB_PATH, DB_PATH)
