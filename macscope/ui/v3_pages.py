from __future__ import annotations

"""MacScope 3.0 page renderers (extend V2 pages without replacing them)."""

from typing import Any

import pandas as pd
import streamlit as st

from macscope.annotations import (
    get_note,
    is_favorited,
    is_pinned,
    list_annotations,
    remove_annotation,
    upsert_annotation,
)
from macscope.assistant import answer_question
from macscope.cleanup import advisor_rows
from macscope.search import search_inventory
from macscope.startup_analyzer import score_startup_impact
from macscope.storage_explorer import build_storage_tree, treemap_dataframe
from macscope.timeline import list_timeline
from macscope.ui.chrome import impact_badge, open_folder, render_folder_shortcuts, risk_badge
from macscope.ui.inventory_view import render_detail_panel, render_inventory, rows_to_records
from macscope.ui.layout import metrics_row, page_header
from macscope.updates import collect_update_notices
from models import Snapshot
from snapshot import get_relationships, row_as_dict
from utils import format_bytes, json_loads


def render_timeline() -> None:
    page_header(
        "System Timeline",
        "Persistent history of inventory changes and management actions derived from snapshots and the action log.",
    )
    event_type = st.selectbox(
        "Filter type",
        ["All"]
        + sorted(
            {
                "software_installed",
                "software_removed",
                "software_updated",
                "startup_changed",
                "security_changed",
                "homebrew_changed",
                "docker_changed",
                "python_changed",
                "ai_model_changed",
                "network_changed",
                "management_action",
                "snapshot_created",
            }
        ),
        key="timeline_type",
    )
    events = list_timeline(limit=300, event_type=None if event_type == "All" else event_type)
    metrics_row({"Events": len(events), "Filter": event_type})
    if not events:
        st.info("No timeline events yet. Collect a snapshot or perform a management action.")
        return
    for event in events:
        with st.expander(f"{event.created_at} · {event.event_type} · {event.title}", expanded=False):
            st.write(event.summary or "—")
            st.caption(f"Source: {event.source} · Category: {event.category or '—'} · Snapshot: {event.snapshot_id or '—'}")
            details = json_loads(event.details_json)
            if details:
                st.json(details)


def render_projects(snap: Snapshot, rows: list[Any]) -> None:
    page_header(
        "Projects",
        "Development projects discovered from configured scan roots, with related inventory grouped together.",
    )
    projects = [r for r in rows if r.category == "Projects"]
    metrics_row({"Projects": len(projects), "Linked items": len([r for r in rows if getattr(r, "project_key", None)])})
    if not projects:
        st.info("No projects discovered. Add roots under Settings and collect a new snapshot.")
        return
    names = {f"{p.name} — {p.path}": p for p in projects}
    choice = st.selectbox("Project", list(names), key="project_select")
    project = names[choice]
    st.markdown(f"**Indicators:** {project.subtype or '—'}")
    st.code(project.path or "")
    if st.button("Open project folder", key="project_open"):
        if project.path:
            open_folder(project.path, label="project folder")
    linked = [r for r in rows if getattr(r, "project_key", None) == getattr(project, "project_key", None) or getattr(r, "project_key", None) == project.path]
    # Also match by path equality for project_key
    linked = [r for r in rows if getattr(r, "project_key", None) in {project.path, getattr(project, "project_key", None)} and r.category != "Projects"]
    buckets = {
        "Applications": [],
        "Processes": [],
        "Network": [],
        "Python": [],
        "Docker": [],
        "AI": [],
        "Startup": [],
        "Other": [],
    }
    for row in linked:
        if row.category in buckets:
            buckets[row.category].append(row)
        elif row.category in {"Login Items", "Background Items"}:
            buckets["Startup"].append(row)
        else:
            buckets["Other"].append(row)
    for title, group in buckets.items():
        with st.expander(f"{title} ({len(group)})", expanded=bool(group) and title in {"Python", "Processes", "Network"}):
            if not group:
                st.caption("None")
                continue
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Name": g.name,
                            "Type": g.item_type,
                            "Status": g.status,
                            "Path": g.path,
                            "Ports": g.network_ports,
                            "Risk": risk_badge(g.risk),
                        }
                        for g in group
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )


def render_cleanup_advisor(snap: Snapshot, rows: list[Any]) -> None:
    page_header(
        "Cleanup Advisor",
        "Recommendations with reason, estimated reclaimable space, confidence, and risk. Review before acting.",
    )
    from inventory import Item
    from utils import json_loads as jl

    items = []
    for row in rows:
        items.append(
            Item(
                category=row.category,
                name=row.name,
                path=row.path,
                status=row.status,
                risk=row.risk,
                protected=row.protected,
                disk_usage=getattr(row, "disk_usage", None),
                modification_date=getattr(row, "modification_date", None),
                orphan_status=bool(getattr(row, "orphan_status", False)),
                classification=row.classification,
                related_application=row.related_application,
                running_state=row.running_state,
                item_type=row.item_type,
                subtype=getattr(row, "subtype", None),
                stable_id=getattr(row, "stable_id", None),
                details=jl(row.details_json),
            )
        )
    data = advisor_rows(items)
    metrics_row(
        {
            "Recommendations": len(data),
            "Est. reclaim bytes": int(sum(d.get("Size bytes") or 0 for d in data)),
        }
    )
    if not data:
        st.success("No cleanup recommendations from the current snapshot.")
        return
    risk_filter = st.multiselect("Risk", sorted({d["Risk"] for d in data}), key="advisor_risk")
    filtered = [d for d in data if not risk_filter or d["Risk"] in risk_filter]
    st.dataframe(pd.DataFrame(filtered), use_container_width=True, hide_index=True, height=420)
    st.caption("Estimated reclaim is best-effort from bounded scans and known sizes.")


def render_storage_explorer(snap: Snapshot, rows: list[Any]) -> None:
    page_header(
        "Storage Explorer",
        "Drill-down storage buckets from inventory and bounded folder scans.",
    )
    deep = st.checkbox("Deep scan (slower)", value=False, key="storage_deep")
    from inventory import Item
    from utils import json_loads as jl

    items = [
        Item(
            category=r.category,
            name=r.name,
            path=r.path,
            disk_usage=getattr(r, "disk_usage", None),
            item_type=r.item_type,
        )
        for r in rows
    ]
    nodes = build_storage_tree(items, deep=deep)
    metrics_row({n.name: format_bytes(n.size) for n in nodes[:6]})
    df = pd.DataFrame(treemap_dataframe(nodes))
    if not df.empty:
        try:
            import plotly.express as px

            fig = px.treemap(df, path=["Bucket", "Item"], values="Size bytes", title="Storage overview")
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            st.bar_chart(df.groupby("Bucket")["Size bytes"].sum())
    for node in nodes:
        with st.expander(f"{node.name} · {format_bytes(node.size)}", expanded=False):
            if node.path:
                st.code(node.path)
                if st.button("Reveal folder", key=f"stor_{node.name}"):
                    open_folder(node.path, label=node.name)
            if node.children:
                st.dataframe(
                    pd.DataFrame(
                        [{"Name": c.name, "Size": format_bytes(c.size), "Path": c.path} for c in node.children]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )


def render_startup_analyzer(snap: Snapshot, rows: list[Any]) -> None:
    page_header(
        "Startup Analyzer",
        "Estimated startup impact (Low / Medium / High) from launch configuration and observed process metrics.",
    )
    startup = [r for r in rows if r.category in {"Startup", "Login Items", "Background Items"}]
    levels = {"Low": 0, "Medium": 0, "High": 0}
    records = []
    for row in startup:
        impact = getattr(row, "startup_impact", None) or "Low"
        levels[impact] = levels.get(impact, 0) + 1
        records.append(
            {
                "Name": row.name,
                "Type": row.item_type or row.category,
                "Impact": impact_badge(impact),
                "Startup": row.startup_state,
                "Path": row.path,
                "Risk": risk_badge(row.risk),
                "Explanation": row.explanation,
            }
        )
    metrics_row(levels)
    filt = st.multiselect("Impact", ["Low", "Medium", "High"], key="startup_impact_filter")
    if filt:
        records = [r for r in records if any(f in r["Impact"] for f in filt)]
    st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True, height=480)


def render_search(snap: Snapshot, rows: list[Any]) -> None:
    page_header(
        "Natural Language Search",
        "Local rule-based search over the current snapshot. No cloud AI required.",
    )
    query = st.text_input(
        "Query",
        placeholder="apps using Python · software larger than 5 GB · startup services · AI software · applications by Adobe",
        key="nl_search_q",
    )
    if query:
        hits = search_inventory(query, rows)
        st.caption(f"{len(hits)} match(es)")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Category": h.category,
                        "Name": h.name,
                        "Type": h.item_type,
                        "Risk": h.risk,
                        "Disk": format_bytes(getattr(h, "disk_usage", None)),
                        "Path": h.path,
                        "Ports": h.network_ports,
                    }
                    for h in hits[:300]
                ]
            ),
            use_container_width=True,
            hide_index=True,
            height=480,
        )


def render_assistant(snap: Snapshot | None, rows: list[Any]) -> None:
    page_header(
        "Assistant",
        "Answers questions using only local inventory and timeline facts. Never invents data.",
    )
    if snap is None and not rows:
        st.caption("No snapshot loaded — timeline questions may still work.")
    question = st.text_input(
        "Ask about this Mac",
        placeholder="What is using memory? Can I uninstall Docker? What changed yesterday?",
        key="assistant_q",
    )
    if st.button("Answer", key="assistant_go") and question:
        st.markdown(answer_question(question, rows))
    elif question and st.session_state.get("assistant_auto"):
        st.markdown(answer_question(question, rows))


def render_crashes(snap: Snapshot, rows: list[Any]) -> None:
    page_header("Crash History", "Local DiagnosticReports grouped by application.")
    render_inventory("Crash History", rows, categories=["Crashes"], snapshot_label=f"Snapshot #{snap.id}", key_prefix="crash", show_header=False)


def render_permissions(snap: Snapshot, rows: list[Any]) -> None:
    page_header(
        "Permissions Explorer",
        "Privacy permissions from readable TCC databases (Camera, Microphone, Accessibility, and more).",
    )
    render_inventory("Permissions", rows, categories=["Permissions"], snapshot_label=f"Snapshot #{snap.id}", key_prefix="perm", show_header=False)


def render_updates() -> None:
    page_header(
        "Update Awareness",
        "Detect available updates where practical. MacScope never installs updates automatically.",
    )
    if st.button("Refresh update checks", key="updates_refresh"):
        st.session_state["update_notices"] = collect_update_notices()
    notices = st.session_state.get("update_notices") or collect_update_notices()
    st.session_state["update_notices"] = notices
    if not notices:
        st.info("No update information available.")
        return
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Ecosystem": n.ecosystem,
                    "Name": n.name,
                    "Current": n.current or "—",
                    "Latest": n.latest or "—",
                    "Detail": n.detail,
                }
                for n in notices
            ]
        ),
        use_container_width=True,
        hide_index=True,
        height=480,
    )


def render_favorites_and_notes(rows: list[Any]) -> None:
    page_header("Favorites, Pins & Notes", "Personal annotations stored locally in the MacScope database.")
    favs = list_annotations("favorite")
    pins = list_annotations("pin")
    notes = list_annotations("note")
    metrics_row({"Favorites": len(favs), "Pins": len(pins), "Notes": len(notes)})
    by_id = {getattr(r, "stable_id", None): r for r in rows if getattr(r, "stable_id", None)}
    st.subheader("Pinned")
    for p in pins:
        row = by_id.get(p.stable_id)
        st.write(f"📌 {p.display_name or p.stable_id}" + (f" · {row.category}" if row else ""))
    st.subheader("Favorites")
    for f in favs:
        st.write(f"⭐ {f.display_name or f.stable_id}")
    st.subheader("Notes")
    for n in notes:
        with st.expander(n.display_name or n.stable_id):
            st.write(n.value)


def render_enhanced_relationships(snap: Snapshot, rows: list[Any]) -> None:
    page_header(
        "Relationships",
        "Application, project, Homebrew, Docker, and AI relationships with tree and table views.",
    )
    rels = get_relationships(snap.id)
    names = {getattr(r, "stable_id", None): r.name for r in rows if getattr(r, "stable_id", None)}
    rel_type = st.multiselect(
        "Relation types",
        sorted({r.relation_type for r in rels}),
        key="rel_types_v3",
    )
    filtered = [r for r in rels if not rel_type or r.relation_type in rel_type]
    query = st.text_input("Filter", key="rel_q_v3")
    records = []
    for rel in filtered:
        src = names.get(rel.source_stable_id, rel.source_stable_id)
        dst = names.get(rel.target_stable_id, rel.target_stable_id)
        if query and query.lower() not in f"{src} {dst} {rel.relation_type}".lower():
            continue
        records.append(
            {
                "Source": src,
                "Relation": rel.relation_type,
                "Target": dst,
                "Confidence": rel.confidence,
                "Evidence": rel.evidence,
            }
        )
    tab_table, tab_tree = st.tabs(["Table", "Tree"])
    with tab_table:
        st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True, height=480)
    with tab_tree:
        tree: dict[str, list[str]] = {}
        for rec in records:
            tree.setdefault(rec["Source"], []).append(f"{rec['Relation']} → {rec['Target']}")
        for source, children in sorted(tree.items()):
            with st.expander(f"{source} ({len(children)})", expanded=False):
                for child in children:
                    st.markdown(f"- {child}")


def render_item_annotation_controls(row: Any) -> None:
    sid = getattr(row, "stable_id", None)
    if not sid:
        return
    st.markdown("##### Annotations")
    c1, c2, c3 = st.columns(3)
    with c1:
        fav = is_favorited(sid)
        if st.button("Unfavorite" if fav else "Favorite", key=f"fav_{sid}"):
            if fav:
                remove_annotation(sid, "favorite")
            else:
                upsert_annotation(sid, "favorite", display_name=row.name)
            st.rerun()
    with c2:
        pinned = is_pinned(sid)
        if st.button("Unpin" if pinned else "Pin", key=f"pin_{sid}"):
            if pinned:
                remove_annotation(sid, "pin")
            else:
                upsert_annotation(sid, "pin", display_name=row.name)
            st.rerun()
    with c3:
        note = st.text_area("Note", value=get_note(sid), key=f"note_{sid}")
        if st.button("Save note", key=f"note_save_{sid}"):
            upsert_annotation(sid, "note", value=note, display_name=row.name)
            st.success("Note saved.")


def render_tools_drawer() -> None:
    page_header("Tools & Folders", "Quick access to MacScope data locations and recent local activity.")
    render_folder_shortcuts()
    st.subheader("Recent timeline activity")
    events = list_timeline(limit=15)
    if not events:
        st.caption("No recent timeline events.")
        return
    for event in events:
        st.markdown(f"- **{event.created_at}** — {event.title}")
