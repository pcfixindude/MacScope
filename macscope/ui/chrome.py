from __future__ import annotations

"""Shared UI chrome: command palette, folder openers, badges."""

from pathlib import Path

import streamlit as st

from config import BACKUPS_DIR, DATA_ROOT, LOGS_DIR, REPORTS_DIR
from macscope.settings import load_settings
from utils import run_command


def open_folder(path: Path | str, *, label: str = "folder") -> None:
    target = Path(path).expanduser()
    target.mkdir(parents=True, exist_ok=True)
    rc, out, err = run_command(["open", str(target)], timeout=15)
    if rc == 0:
        st.success(f"Opened {label}: {target}")
    else:
        st.error(err or out or f"Could not open {label}.")


def render_folder_shortcuts() -> None:
    settings = load_settings()
    report_dir = Path(settings.report_output_folder or REPORTS_DIR).expanduser()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("Open Reports Folder", key="chrome_reports", use_container_width=True):
            open_folder(report_dir, label="reports folder")
    with c2:
        if st.button("Open Logs Folder", key="chrome_logs", use_container_width=True):
            open_folder(LOGS_DIR, label="logs folder")
    with c3:
        if st.button("Open Backups Folder", key="chrome_backups", use_container_width=True):
            open_folder(BACKUPS_DIR, label="backups folder")
    with c4:
        if st.button("Open Application Support", key="chrome_data", use_container_width=True):
            open_folder(DATA_ROOT, label="MacScope data folder")


COMMAND_TARGETS = [
    "Dashboard",
    "System Timeline",
    "Projects",
    "Cleanup Advisor",
    "Storage Explorer",
    "Startup Analyzer",
    "Search",
    "Assistant",
    "Crash History",
    "Permissions",
    "Updates",
    "Relationships",
    "Snapshots",
    "Reports",
    "Action History",
    "Diagnostics",
    "Settings",
    "About",
    "Applications",
    "Running Processes",
    "Homebrew",
    "Python",
    "Node",
    "Docker",
    "AI Software and Models",
    "Network",
]


def render_command_palette(current_pages: list[str]) -> str | None:
    """Return a page name when the user jumps via the palette."""
    with st.sidebar.expander("Command palette", expanded=False):
        st.caption("Type to jump. Shortcuts: collect = sidebar buttons.")
        choice = st.selectbox(
            "Go to",
            options=["—"] + [p for p in COMMAND_TARGETS if p in current_pages or p in COMMAND_TARGETS],
            key="command_palette",
        )
        if choice and choice != "—":
            if st.button("Jump", key="command_palette_go", use_container_width=True):
                return choice
    return None


def impact_badge(level: str | None) -> str:
    level = (level or "Unknown").title()
    return {"Low": "🟢 Low", "Medium": "🟡 Medium", "High": "🔴 High"}.get(level, f"⚪ {level}")


def risk_badge(risk: str | None) -> str:
    risk = risk or "Unknown"
    mapping = {
        "Safe": "🟢 Safe",
        "Caution": "🟡 Caution",
        "Protected": "🔒 Protected",
        "Orphaned": "🟠 Orphaned",
        "Unknown": "⚪ Unknown",
    }
    return mapping.get(risk, risk)
