from __future__ import annotations

"""MacScope 2.0 — local macOS inventory and management application."""

from database import init_db
from config import APP_NAME, APP_VERSION, ensure_data_dirs, migrate_legacy_data

ensure_data_dirs()
migrate_legacy_data()
init_db()

import streamlit as st

from collector import collect_all
from macscope.settings import load_settings
from macscope.ui.pages import (
    render_about,
    render_action_history,
    render_cleanup,
    render_dashboard,
    render_diagnostics,
    render_inventory_page,
    render_relationships,
    render_reports,
    render_settings,
    render_snapshots,
)
from snapshot import latest_snapshot, save_snapshot

st.set_page_config(page_title=f"{APP_NAME} {APP_VERSION}", page_icon="🔭", layout="wide")


def _bump_refresh() -> None:
    st.session_state.refresh_key = st.session_state.get("refresh_key", 0) + 1
    st.cache_data.clear()


@st.cache_data(show_spinner=False)
def load_latest(cache_key: int = 0):
    return latest_snapshot()


def collect_now(*, deep: bool = False, note: str = "", name: str | None = None) -> None:
    bar = st.progress(0.0, text="Starting…")
    result = collect_all(lambda n, t: bar.progress(min(float(n), 1.0), text=t), deep=deep)
    sid = save_snapshot(
        result.items,
        note=note,
        collector_errors=result.errors,
        relationships=result.relationships,
        name=name,
        duration_seconds=result.duration_seconds,
    )
    _bump_refresh()
    bar.empty()
    msg = f"Snapshot #{sid} collected with {len(result.items):,} items in {result.duration_seconds:.1f}s."
    if result.errors:
        msg += f" {len(result.errors)} collector warning(s) — see Diagnostics."
    st.success(msg)


PAGES = [
    "Dashboard",
    "Applications",
    "Running Processes",
    "Startup Overview",
    "Login and Background Items",
    "Launch Agents",
    "Launch Daemons",
    "Homebrew",
    "Python",
    "Node",
    "Docker",
    "AI Software and Models",
    "Network",
    "Storage",
    "Security",
    "Relationships",
    "Cleanup Review",
    "Snapshots",
    "Reports",
    "Action History",
    "Diagnostics",
    "Settings",
    "About",
]


with st.sidebar:
    st.title(APP_NAME)
    st.caption(f"Version {APP_VERSION} · Local only")
    page = st.radio("Navigate", PAGES, label_visibility="collapsed")
    st.divider()
    if st.button("Collect snapshot", use_container_width=True, type="primary"):
        collect_now()
    if st.button("Deep scan snapshot", use_container_width=True):
        collect_now(deep=True, note="Deep scan")
    if st.button("Refresh view", use_container_width=True):
        _bump_refresh()
        st.rerun()

settings = load_settings()
if settings.automatic_snapshot_on_startup and "auto_snap_done" not in st.session_state:
    st.session_state.auto_snap_done = True
    collect_now(note="Automatic startup snapshot")

snap, rows = load_latest(st.session_state.get("refresh_key", 0))

# Pages that work without a snapshot
if page == "Settings":
    render_settings()
elif page == "About":
    render_about()
elif page == "Action History":
    render_action_history()
elif page == "Diagnostics":
    render_diagnostics(snap, rows if snap else [])
elif not snap:
    st.title(APP_NAME)
    st.info("No inventory snapshot yet. Click **Collect snapshot** in the sidebar to begin.")
    st.stop()
elif page == "Dashboard":
    render_dashboard(snap, rows)
elif page == "Applications":
    render_inventory_page(
        "Applications",
        "Installed applications from standard macOS locations.",
        rows,
        categories=["Applications"],
        snapshot_label=f"Snapshot #{snap.id}",
        key_prefix="apps",
    )
elif page == "Running Processes":
    render_inventory_page(
        "Running Processes",
        "Live process inventory from the latest snapshot.",
        rows,
        categories=["Processes"],
        snapshot_label=f"Snapshot #{snap.id}",
        key_prefix="procs",
    )
elif page == "Startup Overview":
    render_inventory_page(
        "Startup Overview",
        "Launch items, login items, and background entries.",
        rows,
        categories=["Startup", "Login Items", "Background Items"],
        snapshot_label=f"Snapshot #{snap.id}",
        key_prefix="startup",
    )
elif page == "Login and Background Items":
    render_inventory_page(
        "Login and Background Items",
        "Login Items and Background Task Management entries where accessible.",
        rows,
        categories=["Login Items", "Background Items"],
        snapshot_label=f"Snapshot #{snap.id}",
        key_prefix="login",
    )
elif page == "Launch Agents":
    agent_rows = [
        r
        for r in rows
        if r.category == "Startup" and "LaunchAgent" in (r.item_type or r.vendor or "")
    ]
    render_inventory_page(
        "Launch Agents",
        "User and system LaunchAgents.",
        agent_rows,
        snapshot_label=f"Snapshot #{snap.id}",
        key_prefix="agents",
    )
elif page == "Launch Daemons":
    daemon_rows = [
        r
        for r in rows
        if r.category == "Startup" and "LaunchDaemon" in (r.item_type or r.vendor or "")
    ]
    render_inventory_page(
        "Launch Daemons",
        "System LaunchDaemons. Elevated changes remain guarded or manual in Version 2.",
        daemon_rows,
        snapshot_label=f"Snapshot #{snap.id}",
        key_prefix="daemons",
    )
elif page == "Homebrew":
    render_inventory_page(
        "Homebrew",
        "Formulas, casks, and Homebrew services.",
        rows,
        categories=["Homebrew", "Services"],
        snapshot_label=f"Snapshot #{snap.id}",
        key_prefix="brew",
    )
elif page == "Python":
    render_inventory_page(
        "Python",
        "Interpreters, virtual environments, Conda, and pyenv installations.",
        rows,
        categories=["Python"],
        snapshot_label=f"Snapshot #{snap.id}",
        key_prefix="py",
    )
elif page == "Node":
    render_inventory_page(
        "Node",
        "Node runtimes, global packages, and project node_modules.",
        rows,
        categories=["Node"],
        snapshot_label=f"Snapshot #{snap.id}",
        key_prefix="node",
    )
elif page == "Docker":
    render_inventory_page(
        "Docker",
        "Containers, images, volumes, networks, and disk usage.",
        rows,
        categories=["Docker"],
        snapshot_label=f"Snapshot #{snap.id}",
        key_prefix="docker",
    )
elif page == "AI Software and Models":
    render_inventory_page(
        "AI Software and Models",
        "Local AI apps, model files, and listening AI servers.",
        rows,
        categories=["AI"],
        snapshot_label=f"Snapshot #{snap.id}",
        key_prefix="ai",
    )
elif page == "Network":
    render_inventory_page(
        "Network",
        "Listening ports with binding classification and common-port hints.",
        rows,
        categories=["Network"],
        snapshot_label=f"Snapshot #{snap.id}",
        key_prefix="net",
    )
elif page == "Storage":
    render_inventory_page(
        "Storage",
        "Bounded volume and folder usage summaries from the latest snapshot.",
        rows,
        categories=["Storage"],
        snapshot_label=f"Snapshot #{snap.id}",
        key_prefix="storage",
    )
elif page == "Security":
    render_inventory_page(
        "Security",
        "Local security posture summaries. MacScope is not antivirus software.",
        rows,
        categories=["Security"],
        snapshot_label=f"Snapshot #{snap.id}",
        key_prefix="sec",
    )
elif page == "Relationships":
    render_relationships(snap, rows)
elif page == "Cleanup Review":
    render_cleanup(snap, rows)
elif page == "Snapshots":
    render_snapshots(snap, rows)
elif page == "Reports":
    render_reports(snap, rows)
else:
    st.error(f"Unknown page: {page}")
