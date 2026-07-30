from __future__ import annotations

import platform
import shutil
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import streamlit as st

from analyzer import health_score
from compare import compare_snapshots
from config import (
    APP_NAME,
    APP_VERSION,
    CACHE_DIR,
    DATA_ROOT,
    DB_PATH,
    LOG_PATH,
    REPORTS_DIR,
    VERSION_PATH,
)
from database import SessionLocal, get_schema_version
from inventory import Item
from macscope.backup import list_backups, restore_file_backup
from macscope.cleanup import find_cleanup_candidates
from macscope.reports import (
    export_csv_category,
    export_html_report,
    export_json_snapshot,
    export_markdown_summary,
)
from macscope.settings import Settings, load_settings, save_settings
from macscope.ui.actions_panel import render_actions_for_row
from macscope.ui.inventory_view import render_detail_panel, render_inventory, rows_to_records
from macscope.ui.layout import consume_action_token, ensure_action_token, metrics_row, page_header
from models import Event, Snapshot
from snapshot import delete_snapshot, get_relationships, get_snapshot, list_snapshots, row_as_dict
from utils import format_bytes, json_loads, run_command


def _version() -> str:
    try:
        return VERSION_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return APP_VERSION


def _snapshot_meta(snap: Snapshot) -> dict[str, Any]:
    return {
        "id": snap.id,
        "created_at": str(snap.created_at),
        "hostname": snap.hostname,
        "note": snap.note,
        "name": getattr(snap, "name", None),
        "duration_seconds": getattr(snap, "duration_seconds", None),
    }


def _count(rows: list[Any], category: str) -> int:
    return len([r for r in rows if getattr(r, "category", None) == category])


def _rows_to_items(rows: list[Any]) -> list[Item]:
    items: list[Item] = []
    for row in rows:
        items.append(
            Item(
                category=row.category,
                name=row.name,
                path=row.path,
                status=row.status,
                vendor=row.vendor,
                version=row.version,
                cpu=row.cpu,
                memory=row.memory,
                risk=row.risk,
                protected=row.protected,
                details=json_loads(row.details_json),
                label=row.label,
                item_type=row.item_type,
                executable_path=row.executable_path,
                publisher=row.publisher,
                installation_source=row.installation_source,
                running_state=row.running_state,
                startup_state=row.startup_state,
                network_ports=row.network_ports,
                classification=row.classification,
                explanation=row.explanation,
                related_application=row.related_application,
                available_actions=json_loads(row.available_actions, default=[]),
                stable_id=getattr(row, "stable_id", None),
                technical_name=getattr(row, "technical_name", None),
                subtype=getattr(row, "subtype", None),
                bundle_id=getattr(row, "bundle_id", None),
                signing_identity=getattr(row, "signing_identity", None),
                team_identifier=getattr(row, "team_identifier", None),
                configuration_path=getattr(row, "configuration_path", None),
                command=getattr(row, "command", None),
                user_owner=getattr(row, "user_owner", None),
                group_owner=getattr(row, "group_owner", None),
                enabled_status=getattr(row, "enabled_status", None),
                pid=getattr(row, "pid", None),
                parent_process=getattr(row, "parent_process", None),
                disk_usage=getattr(row, "disk_usage", None),
                install_date=getattr(row, "install_date", None),
                modification_date=getattr(row, "modification_date", None),
                confidence=getattr(row, "confidence", None),
                removal_guidance=getattr(row, "removal_guidance", None),
                orphan_status=bool(getattr(row, "orphan_status", False)),
                build_number=getattr(row, "build_number", None),
                related_package=getattr(row, "related_package", None),
                related_service=getattr(row, "related_service", None),
            )
        )
    return items


def _system_metrics(rows: list[Any]) -> dict[str, str]:
    cpu_rows = [r for r in rows if getattr(r, "cpu", None) is not None]
    mem_rows = [r for r in rows if getattr(r, "memory", None) is not None]
    disk_rows = [r for r in rows if getattr(r, "disk_usage", None) is not None]
    top_cpu = max(cpu_rows, key=lambda r: r.cpu or 0, default=None)
    top_mem = max(mem_rows, key=lambda r: r.memory or 0, default=None)
    total_disk = sum(getattr(r, "disk_usage", 0) or 0 for r in disk_rows)
    return {
        "Top CPU": f"{top_cpu.name} ({top_cpu.cpu:.1f}%)" if top_cpu and top_cpu.cpu is not None else "—",
        "Top memory": f"{top_mem.name} ({top_mem.memory:.1f}%)" if top_mem and top_mem.memory is not None else "—",
        "Indexed disk": format_bytes(total_disk) if total_disk else "—",
    }


def render_dashboard(snap: Snapshot, rows: list[Any]) -> None:
    page_header(
        "System Dashboard",
        "Overview of the latest inventory snapshot, health score, and recent activity.",
    )
    score, notes = health_score(rows)
    orphaned = len([r for r in rows if getattr(r, "orphan_status", False) or r.classification == "Orphaned"])
    security_rows = [r for r in rows if r.category == "Security"]

    metrics_row(
        {
            "Health score": f"{score}/100",
            "Applications": _count(rows, "Applications"),
            "Processes": _count(rows, "Processes"),
            "Startup items": _count(rows, "Startup"),
        }
    )
    metrics_row(
        {
            "Network listeners": _count(rows, "Network"),
            "Homebrew": _count(rows, "Homebrew"),
            "Python envs": _count(rows, "Python"),
            "Docker resources": _count(rows, "Docker"),
            "AI assets": _count(rows, "AI"),
        },
        columns=5,
    )
    metrics_row(
        {
            "Snapshot": f"#{snap.id}",
            "Orphaned items": orphaned,
            **_system_metrics(rows),
        },
        columns=4,
    )

    if notes:
        st.warning(" · ".join(notes))

    with st.expander("Security status summary", expanded=False):
        if security_rows:
            st.dataframe(
                pd.DataFrame(
                    [{"Name": r.name, "Status": r.status, "Risk": r.risk, "Explanation": r.explanation} for r in security_rows]
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("No security items in this snapshot.")

    caution = [r for r in rows if r.risk in {"Caution", "Orphaned", "Unknown"} and not r.protected]
    st.subheader("Items needing attention")
    if caution:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Name": r.name,
                        "Category": r.category,
                        "Risk": r.risk,
                        "Classification": r.classification,
                        "Explanation": r.explanation,
                    }
                    for r in caution[:200]
                ]
            ),
            use_container_width=True,
            hide_index=True,
            height=320,
        )
    else:
        st.success("No caution, orphaned, or unknown items in this snapshot.")

    st.subheader("Recent events")
    with SessionLocal() as db:
        events = db.query(Event).order_by(Event.id.desc()).limit(15).all()
    if events:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Time": e.created_at,
                        "Action": e.action,
                        "Target": e.display_name or e.target,
                        "Result": e.result,
                    }
                    for e in events
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("No management actions recorded yet.")


def render_inventory_page(
    title: str,
    explanation: str,
    rows: list[Any],
    *,
    categories: list[str] | None = None,
    snapshot_label: str = "",
    key_prefix: str = "inv",
    on_after_action: Callable[[], None] | None = None,
) -> list[dict[str, Any]]:
    page_header(title, explanation)
    filtered = render_inventory(
        "",
        rows,
        categories=categories,
        snapshot_label=snapshot_label,
        key_prefix=key_prefix,
        show_header=False,
    )
    if filtered:
        labels = [
            f"{r.get('Name')} · {r.get('Type') or r.get('Category')} · {r.get('Path') or r.get('Label') or r.get('ID')}"
            for r in filtered
        ]
        choice = st.session_state.get(f"{key_prefix}_inspect")
        if choice in labels:
            render_actions_for_row(filtered[labels.index(choice)]["_row"], on_after_action)
    return filtered


def render_relationships(snap: Snapshot, rows: list[Any]) -> None:
    page_header(
        "Relationships",
        "Links between inventory items inferred during collection (startup, package, and service relationships).",
    )
    rels = get_relationships(snap.id)
    if not rels:
        st.info("No relationships recorded for this snapshot.")
        return

    stable_names = {getattr(r, "stable_id", None): r.name for r in rows if getattr(r, "stable_id", None)}
    records = [
        {
            "Source": stable_names.get(rel.source_stable_id, rel.source_stable_id),
            "Target": stable_names.get(rel.target_stable_id, rel.target_stable_id),
            "Type": rel.relation_type,
            "Confidence": f"{rel.confidence:.0%}",
            "Evidence": rel.evidence or "",
            "Source ID": rel.source_stable_id,
            "Target ID": rel.target_stable_id,
        }
        for rel in rels
    ]
    query = st.text_input("Search relationships", key="rel_search", placeholder="Source, target, type, evidence…")
    if query:
        q = query.lower()
        records = [
            r
            for r in records
            if any(q in str(r.get(col, "")).lower() for col in ("Source", "Target", "Type", "Evidence", "Source ID", "Target ID"))
        ]
    st.caption(f"{len(records):,} relationships")
    st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True, height=420)

    with st.expander("Relationship details", expanded=False):
        for rel in rels[:100]:
            st.markdown(
                f"**{rel.relation_type}** · {rel.source_stable_id} → {rel.target_stable_id} "
                f"({rel.confidence:.0%})"
            )
            if rel.evidence:
                st.caption(rel.evidence)


def render_cleanup(snap: Snapshot, rows: list[Any]) -> None:
    page_header(
        "Cleanup candidates",
        "Heuristic cleanup suggestions from orphaned startup items, Docker, Python, Node, AI, and storage scans.",
    )
    items = _rows_to_items(rows)
    candidates = find_cleanup_candidates(items)
    if not candidates:
        st.success("No cleanup candidates identified for this snapshot.")
        return

    query = st.text_input("Search candidates", key="cleanup_search", placeholder="Name, reason, type…")
    filtered = candidates
    if query:
        q = query.lower()
        filtered = [
            c
            for c in candidates
            if q in c.name.lower()
            or q in c.reason.lower()
            or q in c.candidate_type.lower()
            or q in (c.path or "").lower()
        ]

    st.caption(f"{len(filtered):,} candidates")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Type": c.candidate_type,
                    "Name": c.name,
                    "Path": c.path,
                    "Size": format_bytes(c.size),
                    "Risk": c.risk,
                    "Confidence": f"{c.confidence:.0%}",
                    "Recommended action": c.recommended_action,
                }
                for c in filtered
            ]
        ),
        use_container_width=True,
        hide_index=True,
        height=420,
    )

    for index, candidate in enumerate(filtered[:25]):
        with st.expander(f"{candidate.candidate_type}: {candidate.name}", expanded=False):
            st.markdown(f"**Reason:** {candidate.reason}")
            st.markdown(f"**Recommended action:** {candidate.recommended_action}")
            if candidate.path:
                st.code(candidate.path)
            if candidate.related_software:
                st.caption(f"Related software: {candidate.related_software}")


def render_snapshots(snap: Snapshot, rows: list[Any]) -> None:
    page_header(
        "Snapshots",
        "Browse saved inventory snapshots and compare changes over time.",
    )
    snaps = list_snapshots()
    st.subheader("Latest snapshot")
    st.markdown(
        f"**#{snap.id}** · {snap.created_at} · {snap.hostname} · {len(rows):,} items"
        + (f" · {snap.note}" if snap.note else "")
    )

    st.subheader("Compare snapshots")
    if len(snaps) < 2:
        st.info("Collect at least two snapshots to compare.")
    else:
        options = {f"#{s.id} — {s.created_at} — {s.hostname}": s.id for s in snaps}
        labels = list(options.keys())
        left = st.selectbox("Baseline (older)", labels, index=min(1, len(labels) - 1), key="snap_left")
        right = st.selectbox("Compare (newer)", labels, index=0, key="snap_right")
        if options[left] == options[right]:
            st.warning("Select two different snapshots.")
        elif st.button("Compare", type="primary", key="snap_compare_btn"):
            older_id, newer_id = options[left], options[right]
            _, older_rows = get_snapshot(older_id)
            _, newer_rows = get_snapshot(newer_id)
            if older_id > newer_id:
                older_rows, newer_rows = newer_rows, older_rows
                st.caption("Snapshots were ordered so the earlier snapshot is the baseline.")
            st.session_state["compare_result"] = compare_snapshots(older_rows, newer_rows)

        result = st.session_state.get("compare_result")
        if result:

            def _section(title: str, entries: list) -> None:
                with st.expander(f"{title} ({len(entries)})", expanded=False):
                    if not entries:
                        st.caption("None")
                        return
                    for entry in entries:
                        with st.expander(
                            f"{entry.get('Name')} · {entry.get('Category')} · "
                            f"{entry.get('Path') or entry.get('Label') or ''}",
                            expanded=False,
                        ):
                            render_detail_panel(entry)
                            if entry.get("changes"):
                                st.markdown("**Changes**")
                                st.json(entry["changes"])

            _section("Added items", result.added)
            _section("Removed items", result.removed)
            _section("Changed items", result.changed)
            _section("Newly running processes", result.newly_running)
            _section("Newly enabled startup items", result.newly_enabled_startup)
            _section("Newly opened listening ports", result.newly_opened_ports)
            _section("Version changes", result.version_changes)
            _section("Service status changes", result.service_status_changes)
            _section("New applications", result.new_applications)
            _section("Removed applications", result.removed_applications)
            _section("AI model changes", result.new_ai_models + result.removed_ai_models)

    st.subheader("All snapshots")
    snap_df = pd.DataFrame(
        [
            {
                "ID": s.id,
                "Created": s.created_at,
                "Computer": s.hostname,
                "Note": s.note,
                "Duration (s)": getattr(s, "duration_seconds", None),
            }
            for s in snaps
        ]
    )
    st.dataframe(snap_df, use_container_width=True, hide_index=True)

    if snaps:
        delete_choice = st.selectbox(
            "Delete snapshot",
            [f"#{s.id} — {s.created_at}" for s in snaps if s.id != snap.id],
            key="snap_delete_choice",
            index=None,
            placeholder="Select a snapshot to delete…",
        )
        if delete_choice:
            delete_id = int(delete_choice.split("—")[0].strip().lstrip("#"))
            confirm = st.checkbox("I understand this permanently deletes the snapshot and its items.", key="snap_del_confirm")
            token = ensure_action_token(f"delete_snap_{delete_id}")
            if st.button("Delete selected snapshot", disabled=not confirm, key="snap_delete_btn"):
                if consume_action_token(token):
                    delete_snapshot(delete_id)
                    st.success(f"Deleted snapshot #{delete_id}.")
                    st.rerun()
                else:
                    st.warning("This action was already processed.")


def render_reports(snap: Snapshot, rows: list[Any]) -> None:
    page_header(
        "Reports & exports",
        "Export the current snapshot to HTML, CSV, JSON, or Markdown. Files are written to your report output folder.",
    )
    records = rows_to_records(rows)
    meta = _snapshot_meta(snap)
    score, notes = health_score(rows)
    summary = {
        "Health score": f"{score}/100",
        "Items": len(rows),
        "Applications": _count(rows, "Applications"),
        "Processes": _count(rows, "Processes"),
        "Notes": " · ".join(notes) if notes else "None",
    }

    with SessionLocal() as db:
        events = db.query(Event).order_by(Event.id.desc()).limit(100).all()
    action_rows = [
        {
            "created_at": str(e.created_at),
            "action": e.action,
            "target": e.target,
            "result": e.result,
            "message": e.message,
        }
        for e in events
    ]

    categories = sorted({r.category for r in rows})
    sections = {cat: [row_as_dict(r) for r in rows if r.category == cat] for cat in categories}
    security = [row_as_dict(r) for r in rows if r.category == "Security"]
    cleanup = [
        {
            "name": c.name,
            "reason": c.reason,
            "risk": c.risk,
        }
        for c in find_cleanup_candidates(_rows_to_items(rows))[:100]
    ]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("Export HTML report", key="rep_html", use_container_width=True):
            path = export_html_report(meta, summary, sections, action_rows, security, cleanup)
            st.success(f"Wrote {path}")
    with c2:
        if st.button("Export JSON snapshot", key="rep_json", use_container_width=True):
            path = export_json_snapshot(meta, records)
            st.success(f"Wrote {path}")
    with c3:
        export_cat = st.selectbox("CSV category", categories, key="rep_csv_cat")
        if st.button("Export CSV category", key="rep_csv", use_container_width=True):
            cat_records = [r for r in records if r.get("Category") == export_cat]
            path = export_csv_category(export_cat, cat_records)
            st.success(f"Wrote {path}")
    with c4:
        if st.button("Export Markdown summary", key="rep_md", use_container_width=True):
            path = export_markdown_summary(meta, summary, action_rows)
            st.success(f"Wrote {path}")

    settings = load_settings()
    report_dir = Path(settings.report_output_folder or REPORTS_DIR).expanduser()
    report_dir.mkdir(parents=True, exist_ok=True)
    st.caption(f"Report output folder: `{report_dir}`")
    if st.button("Open reports folder", key="rep_open_folder"):
        rc, out, err = run_command(["open", str(report_dir)], timeout=15)
        if rc == 0:
            st.success(f"Opened {report_dir}")
        else:
            st.error(err or out or "Could not open the reports folder.")


def render_action_history() -> None:
    page_header(
        "Action history",
        "Audit log of management actions performed from MacScope, with restore options when backups exist.",
    )
    query = st.text_input("Search actions", key="hist_search", placeholder="Action, target, result…")
    with SessionLocal() as db:
        events = db.query(Event).order_by(Event.id.desc()).limit(500).all()

    if query:
        q = query.lower()
        events = [
            e
            for e in events
            if q in e.action.lower()
            or q in e.target.lower()
            or q in (e.result or "").lower()
            or q in (e.message or "").lower()
        ]

    if not events:
        st.info("No management actions recorded yet.")
        return

    for event in events[:50]:
        with st.expander(
            f"{event.created_at} · {event.action} · {event.display_name or event.target} · {event.result}",
            expanded=False,
        ):
            st.markdown(f"**Target:** {event.target}")
            if event.message:
                st.markdown(f"**Message:** {event.message}")
            if event.command_display:
                st.code(event.command_display)
            if event.stdout:
                st.text(event.stdout)
            if event.stderr:
                st.text(event.stderr)
            if event.backup_path:
                st.caption(f"Backup: {event.backup_path}")
            if event.restore_available and event.backup_path:
                token = ensure_action_token(f"restore_event_{event.id}")
                if st.button("Restore from backup", key=f"restore_{event.id}"):
                    if consume_action_token(token):
                        try:
                            restored = restore_file_backup(event.backup_path)
                            st.success(f"Restored to {restored}")
                        except (FileNotFoundError, PermissionError, OSError) as exc:
                            st.error(str(exc))
                    else:
                        st.warning("This action was already processed.")

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Time": e.created_at,
                    "Action": e.action,
                    "Target": e.display_name or e.target,
                    "Result": e.result,
                    "Restore": "Yes" if e.restore_available else "No",
                }
                for e in events
            ]
        ),
        use_container_width=True,
        hide_index=True,
        height=420,
    )


def render_diagnostics(snap: Snapshot | None, rows: list[Any]) -> None:
    page_header(
        "Diagnostics",
        "Environment details, collector availability, and troubleshooting tools.",
    )
    settings = load_settings()
    commands = {
        "brew": shutil.which("brew"),
        "docker": shutil.which("docker"),
        "npm": shutil.which("npm"),
        "conda": shutil.which("conda"),
        "pyenv": shutil.which("pyenv"),
        "ollama": shutil.which("ollama"),
        "launchctl": shutil.which("launchctl"),
        "sfltool": shutil.which("sfltool"),
    }

    metrics_row(
        {
            "App version": _version(),
            "Python": platform.python_version(),
            "macOS": platform.mac_ver()[0] or platform.platform(),
            "Schema": str(get_schema_version()),
        },
        columns=4,
    )

    st.subheader("Paths")
    st.code(
        "\n".join(
            [
                f"Database: {DB_PATH}",
                f"Log: {LOG_PATH}",
                f"Data root: {DATA_ROOT}",
                f"Cache: {CACHE_DIR}",
            ]
        )
    )

    st.subheader("Command availability")
    st.dataframe(
        pd.DataFrame([{"Command": name, "Path": path or "Not found"} for name, path in commands.items()]),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Collector enablement")
    enabled = settings.collectors_enabled or {}
    st.dataframe(
        pd.DataFrame([{"Collector": name, "Enabled": "Yes" if on else "No"} for name, on in sorted(enabled.items())]),
        use_container_width=True,
        hide_index=True,
    )

    if snap:
        errors = json_loads(getattr(snap, "collector_errors", None), default=[])
        st.subheader("Collector errors from latest snapshot")
        if not errors:
            st.success("No collector errors recorded for the latest snapshot.")
        else:
            for err in errors:
                st.error(f"{err.get('collector')}: {err.get('error')}")

        st.subheader("Latest snapshot")
        st.code(
            "\n".join(
                [
                    f"Snapshot: #{snap.id} @ {snap.created_at}",
                    f"Hostname: {snap.hostname}",
                    f"Items: {len(rows)}",
                    f"Duration: {getattr(snap, 'duration_seconds', '—')}s",
                ]
            )
        )

    st.subheader("Maintenance")
    token = ensure_action_token("clear_cache")
    if st.button("Clear cache directory", key="diag_clear_cache"):
        if consume_action_token(token):
            try:
                if CACHE_DIR.exists():
                    for child in CACHE_DIR.iterdir():
                        if child.is_file():
                            child.unlink()
                        elif child.is_dir():
                            shutil.rmtree(child)
                st.success("Cache directory cleared.")
            except OSError as exc:
                st.error(str(exc))
        else:
            st.warning("This action was already processed.")

    if st.button("Run collector smoke test", key="diag_collect_test"):
        from collector import collect_all

        with st.spinner("Running collectors…"):
            result = collect_all()
        st.success(f"Smoke test completed: {len(result.items):,} items, {len(result.errors)} error(s).")
        if result.errors:
            for err in result.errors:
                st.error(f"{err.get('collector')}: {err.get('error')}")


def render_settings() -> None:
    page_header(
        "Settings",
        "Configure scanning, privacy redaction, collector enablement, and destructive action policy.",
    )
    settings = load_settings()
    destructive_ok = settings.destructive_allowed()

    with st.form("settings_form"):
        st.markdown("#### Display")
        theme = st.selectbox("Theme", ["system", "light", "dark"], index=["system", "light", "dark"].index(settings.theme))
        show_apple = st.checkbox("Show Apple items", value=settings.show_apple_items)
        show_protected = st.checkbox("Show protected items", value=settings.show_protected_items)
        show_advanced = st.checkbox("Show advanced details", value=settings.show_advanced_details)

        st.markdown("#### Scanning")
        project_roots = st.text_area(
            "Project scan roots (one per line)",
            value="\n".join(settings.project_scan_roots),
            height=100,
        )
        custom_project_roots = st.text_area(
            "Custom project roots (one per line)",
            value="\n".join(settings.custom_project_roots or []),
            height=80,
            help="Additional roots merged with project scan roots for Project Intelligence.",
        )
        ai_roots = st.text_area(
            "AI scan roots (one per line)",
            value="\n".join(settings.ai_scan_roots),
            height=100,
        )
        scan_depth = st.number_input("Scan depth", min_value=1, max_value=8, value=int(settings.scan_depth))
        cache_duration = st.number_input(
            "Cache duration (seconds)", min_value=0, max_value=86400, value=int(settings.cache_duration_seconds)
        )
        collector_cache = st.number_input(
            "Collector cache seconds",
            min_value=30,
            max_value=3600,
            value=int(getattr(settings, "collector_cache_seconds", 120) or 120),
        )
        snapshot_retention = st.number_input(
            "Snapshot retention", min_value=1, max_value=500, value=int(settings.snapshot_retention)
        )
        auto_snapshot = st.checkbox("Automatic snapshot on startup", value=settings.automatic_snapshot_on_startup)
        enable_usage = st.checkbox("Enable usage history tracking", value=getattr(settings, "enable_usage_tracking", True))
        enable_automation = st.checkbox("Enable local automation rules", value=getattr(settings, "enable_automation", True))

        st.markdown("#### Privacy redaction")
        redact_username = st.checkbox("Redact username", value=settings.redact_username)
        redact_home = st.checkbox("Redact home path", value=settings.redact_home_path)
        redact_args = st.checkbox("Redact command arguments", value=settings.redact_command_args)
        redact_ips = st.checkbox("Redact local IPs", value=settings.redact_local_ips)
        redact_hostname = st.checkbox("Redact hostname", value=settings.redact_hostname)

        st.markdown("#### Reports & cleanup")
        report_folder = st.text_input("Report output folder", value=settings.report_output_folder or str(REPORTS_DIR))
        prefer_trash = st.checkbox("Prefer Trash for cleanup actions", value=settings.prefer_trash)

        st.markdown("#### Collectors")
        collector_flags = {}
        for name, enabled in sorted((settings.collectors_enabled or {}).items()):
            collector_flags[name] = st.checkbox(f"Enable {name} collector", value=enabled, key=f"col_{name}")
        collect_network = st.checkbox("Collect network listeners", value=settings.collect_network_listeners)
        collect_docker = st.checkbox("Collect Docker", value=settings.collect_docker)
        collect_ai = st.checkbox("Collect AI models", value=settings.collect_ai_models)

        st.markdown("#### Destructive actions")
        st.warning(
            "Destructive actions can stop processes, uninstall software, delete environments, "
            "and move files to Trash. Review each action carefully."
        )
        safety_ack = st.checkbox(
            "I understand MacScope management actions can modify this Mac.",
            value=settings.safety_notice_acknowledged,
        )
        enable_destructive = st.checkbox(
            "Enable destructive actions",
            value=settings.enable_destructive_actions,
            disabled=not safety_ack,
        )
        require_typed = st.checkbox("Require typed confirmation", value=settings.require_typed_confirmation)
        enable_admin = st.checkbox("Enable administrator actions (instructions only)", value=settings.enable_administrator_actions)

        submitted = st.form_submit_button("Save settings", type="primary")

    if submitted:
        updated = Settings(
            theme=theme,
            show_apple_items=show_apple,
            show_protected_items=show_protected,
            show_advanced_details=show_advanced,
            enable_destructive_actions=enable_destructive and safety_ack,
            enable_administrator_actions=enable_admin,
            require_typed_confirmation=require_typed,
            safety_notice_acknowledged=safety_ack,
            snapshot_retention=int(snapshot_retention),
            automatic_snapshot_on_startup=auto_snapshot,
            project_scan_roots=[line.strip() for line in project_roots.splitlines() if line.strip()],
            custom_project_roots=[line.strip() for line in custom_project_roots.splitlines() if line.strip()],
            pinned_project_keys=list(settings.pinned_project_keys or []),
            ai_scan_roots=[line.strip() for line in ai_roots.splitlines() if line.strip()],
            scan_depth=int(scan_depth),
            cache_duration_seconds=int(cache_duration),
            collector_cache_seconds=int(collector_cache),
            enable_usage_tracking=bool(enable_usage),
            enable_automation=bool(enable_automation),
            downloads_notify_gb=float(getattr(settings, "downloads_notify_gb", 20.0) or 20.0),
            storage_growth_notify_gb=float(getattr(settings, "storage_growth_notify_gb", 5.0) or 5.0),
            redact_username=redact_username,
            redact_home_path=redact_home,
            redact_command_args=redact_args,
            redact_local_ips=redact_ips,
            redact_hostname=redact_hostname,
            report_output_folder=report_folder.strip(),
            prefer_trash=prefer_trash,
            collectors_enabled=collector_flags,
            collect_network_listeners=collect_network,
            collect_docker=collect_docker,
            collect_ai_models=collect_ai,
        )
        save_settings(updated)
        st.success("Settings saved.")
        destructive_ok = updated.destructive_allowed()

    if not destructive_ok:
        st.info("Destructive actions remain disabled until you acknowledge the safety notice and enable them above.")

    with st.expander("Current settings (JSON)", expanded=False):
        st.json(asdict(load_settings()))


def render_about() -> None:
    page_header(
        f"About {APP_NAME}",
        "Local-only macOS inventory and management assistant.",
    )
    st.markdown(
        f"""
**Version:** {_version()}

**Privacy:** {APP_NAME} runs entirely on your Mac. Inventory data, snapshots, action logs, and reports
are stored under `{DATA_ROOT}`. No telemetry or cloud upload is performed by this application.

**Data locations:**
- Database: `{DB_PATH}`
- Logs: `{LOG_PATH}`
- Reports: `{REPORTS_DIR}`

**Links**
- [Apple Platform Security](https://support.apple.com/guide/security/welcome/web)
- [Homebrew documentation](https://docs.brew.sh/)
- [Docker documentation](https://docs.docker.com/)

**Python runtime:** {sys.version.split()[0]} on {platform.platform()}
"""
    )

    backups = list_backups(limit=10)
    if backups:
        with st.expander("Recent backups", expanded=False):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Time": b.created_at,
                            "Kind": b.kind,
                            "Source": b.source_path,
                            "Backup": b.backup_path,
                            "Restorable": b.restorable,
                        }
                        for b in backups
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
