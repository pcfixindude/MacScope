from __future__ import annotations

"""MacScope 4.0 page renderers — extend V3 without replacing stable pages."""

from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from macscope.analytics import (
    developer_dashboard_metrics,
    project_dependency_frame,
    relationship_graph_frame,
    storage_treemap_frame,
    timeline_chart_frame,
    usage_chart_frames,
    workspace_map_frame,
)
from macscope.assistant import answer_question_detailed
from macscope.automation import list_rules, list_runs, run_rule, set_rule_enabled
from macscope.explorer import build_explorer_graph, explorer_table
from macscope.knowledge import knowledge_count
from macscope.plugins import plugin_manifest
from macscope.projects import pin_project, project_inventory_summary, unpin_project
from macscope.recommendations import recommendation_rows
from macscope.search import list_saved_searches, save_search, search_inventory
from macscope.timeline import export_timeline_csv, export_timeline_json, list_timeline, timeline_for_period
from macscope.ui.layout import metrics_row, page_header
from macscope.usage import detect_anomalies, list_usage
from macscope.workspaces import (
    MEMBER_TYPES,
    add_member,
    create_workspace,
    delete_workspace,
    list_members,
    list_workspaces,
    remove_member,
    restart_workspace,
    start_workspace,
    stop_workspace,
    update_workspace,
    workspace_status,
)
from models import Snapshot
from utils import format_bytes, json_loads


def _row_details(row: Any) -> dict[str, Any]:
    details = getattr(row, "details", None)
    if isinstance(details, dict):
        return details
    raw = getattr(row, "details_json", None)
    if raw:
        loaded = json_loads(raw)
        return loaded if isinstance(loaded, dict) else {}
    return {}


def render_project_intelligence(snap: Snapshot, rows: list[Any]) -> None:
    page_header(
        "Projects",
        "First-class project intelligence: git, environments, compose, ports, size, activity, and related inventory.",
    )
    projects = [r for r in rows if r.category == "Projects"]
    metrics_row(
        {
            "Projects": len(projects),
            "Pinned": len([p for p in projects if _row_details(p).get("pinned")]),
            "Linked items": len([r for r in rows if getattr(r, "project_key", None)]),
            "Knowledge entries": knowledge_count(),
        }
    )
    if not projects:
        st.info("No projects discovered. Add custom roots in Settings or pin a path.")
        return
    names = {f"{p.name} — {p.path}": p for p in projects}
    choice = st.selectbox("Project", list(names), key="proj_intel_select")
    project = names[choice]
    details = _row_details(project)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Branch", project.version or details.get("git_branch") or "—")
    c2.metric("Git status", project.status or details.get("git_status") or "—")
    c3.metric("Size", format_bytes(project.disk_usage) if project.disk_usage else "—")
    c4.metric("Activity", (project.modification_date or details.get("recent_activity") or "—")[:19])
    st.write(project.explanation or "")
    with st.expander("Package files / requirements / license", expanded=False):
        st.write("Package files:", details.get("package_files") or [])
        st.write("README:", details.get("readme") or "—")
        st.write("License:", details.get("license") or "—")
        st.write("Last commit:", details.get("last_commit") or "—")
        st.write("Requirements (sample):", details.get("requirements") or [])
    b1, b2 = st.columns(2)
    if b1.button("Pin project", key="pin_project_btn"):
        pin_project(project.project_key or project.path or "")
        st.success("Pinned project root saved in Settings.")
    if b2.button("Unpin project", key="unpin_project_btn"):
        unpin_project(project.project_key or project.path or "")
        st.info("Project unpinned.")

    buckets = project_inventory_summary(rows, project.project_key or project.path or "")
    for label, items in buckets.items():
        if not items:
            continue
        st.subheader(label.replace("_", " ").title())
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Name": i.name,
                        "Category": i.category,
                        "Path": i.path,
                        "Status": i.status or i.running_state,
                        "Ports": i.network_ports,
                    }
                    for i in items
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )


def render_workspaces(snap: Snapshot | None, rows: list[Any]) -> None:
    page_header(
        "Workspaces",
        "Complete development environments. Start/stop only assigned members — never unrelated software.",
    )
    workspaces = list_workspaces()
    metrics_row(
        {
            "Workspaces": len(workspaces),
            "Running": len([w for w in workspaces if w.status == "running"]),
            "Pinned": len([w for w in workspaces if w.pinned]),
        }
    )
    with st.expander("Create workspace", expanded=not workspaces):
        name = st.text_input("Name", key="ws_new_name")
        desc = st.text_input("Description", key="ws_new_desc")
        if st.button("Create", key="ws_create") and name.strip():
            create_workspace(name.strip(), desc)
            st.rerun()
    if not workspaces:
        return
    labels = {f"{w.name} (#{w.id})": w for w in workspaces}
    selected = st.selectbox("Workspace", list(labels), key="ws_select")
    ws = labels[selected]
    status = workspace_status(ws.id, rows)
    metrics_row(
        {
            "Status": status.status,
            "Health": status.health,
            "Members": status.members,
            "Observed running": status.running_members,
        }
    )
    for msg in status.messages[:8]:
        st.caption(msg)
    c1, c2, c3, c4, c5 = st.columns(5)
    if c1.button("Start Workspace", key="ws_start"):
        logs = start_workspace(ws.id)
        st.code("\n".join(logs) or "No actions")
    if c2.button("Stop Workspace", key="ws_stop"):
        logs = stop_workspace(ws.id)
        st.code("\n".join(logs) or "No actions")
    if c3.button("Restart Workspace", key="ws_restart"):
        logs = restart_workspace(ws.id)
        st.code("\n".join(logs) or "No actions")
    if c4.button("Pin", key="ws_pin"):
        update_workspace(ws.id, pinned=True)
        st.rerun()
    if c5.button("Delete workspace", key="ws_delete"):
        delete_workspace(ws.id)
        st.rerun()

    members = list_members(ws.id)
    st.subheader("Members")
    if members:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "ID": m.id,
                        "Type": m.member_type,
                        "Label": m.label,
                        "Value": m.value,
                        "Stable ID": m.stable_id,
                    }
                    for m in members
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
        remove_id = st.number_input("Remove member ID", min_value=0, step=1, key="ws_remove_id")
        if st.button("Remove member", key="ws_remove_btn") and remove_id:
            remove_member(int(remove_id))
            st.rerun()
    with st.form("ws_add_member"):
        st.write("Assign resource")
        mtype = st.selectbox("Type", MEMBER_TYPES)
        label = st.text_input("Label")
        value = st.text_input("Value (path, URL, service name, container id, command)")
        stable = st.text_input("Stable ID (optional)")
        if st.form_submit_button("Add member") and value.strip():
            add_member(ws.id, mtype, label or value, value.strip(), stable_id=stable or None)
            st.rerun()


def render_timeline_v4() -> None:
    page_header(
        "System Timeline",
        "Historical intelligence with daily/weekly/monthly views, search, filter, and export.",
    )
    period = st.radio("View", ["daily", "weekly", "monthly", "all"], horizontal=True, key="tl_period")
    query = st.text_input("Search timeline", key="tl_query")
    event_type = st.selectbox(
        "Filter type",
        ["All"]
        + sorted(
            {
                "software_installed",
                "software_removed",
                "software_updated",
                "version_changed",
                "startup_changed",
                "security_changed",
                "permission_changed",
                "storage_growth",
                "project_activity",
                "homebrew_changed",
                "docker_changed",
                "python_changed",
                "environment_changed",
                "ai_model_changed",
                "network_changed",
                "management_action",
                "automation",
                "snapshot_created",
            }
        ),
        key="tl_type_v4",
    )
    if period == "all":
        events = list_timeline(limit=500, event_type=None if event_type == "All" else event_type, query=query or None)
    else:
        events = timeline_for_period(period, limit=500)
        if event_type != "All":
            events = [e for e in events if e.event_type == event_type]
        if query:
            ql = query.lower()
            events = [e for e in events if ql in (e.title or "").lower() or ql in (e.summary or "").lower()]
    metrics_row({"Events": len(events), "Period": period, "Filter": event_type})
    chart = timeline_chart_frame(30)
    if not chart.empty:
        st.plotly_chart(px.bar(chart, x="date", y="count", color="event_type", title="Timeline activity"), use_container_width=True)
    c1, c2 = st.columns(2)
    c1.download_button("Export CSV", export_timeline_csv(events), file_name="macscope-timeline.csv", mime="text/csv")
    c2.download_button("Export JSON", export_timeline_json(events), file_name="macscope-timeline.json", mime="application/json")
    if not events:
        st.info("No timeline events for this view.")
        return
    for event in events[:200]:
        with st.expander(f"{event.created_at} · {event.event_type} · {event.title}", expanded=False):
            st.write(event.summary or "—")
            st.caption(f"Source: {event.source} · Category: {event.category or '—'} · Snapshot: {event.snapshot_id or '—'}")


def render_recommendation_engine(snap: Snapshot, rows: list[Any]) -> None:
    page_header(
        "Cleanup Advisor",
        "Scored recommendations with evidence, impact, risk, and project/timeline references. Never blind deletion.",
    )
    table = recommendation_rows(rows)
    metrics_row({"Recommendations": len(table)})
    if not table:
        st.info("No recommendations from the current snapshot.")
        return
    st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)
    st.caption("Every recommendation explains WHY and asks for review before any destructive action.")


def render_usage_history(snap: Snapshot, rows: list[Any]) -> None:
    page_header("Usage History", "Historical CPU, memory, disk, and launch observations from snapshots.")
    frames = usage_chart_frames(30)
    system = frames["system"]
    if not system.empty:
        if "memory" in system:
            st.plotly_chart(px.line(system, x="created_at", y="memory", title="System memory signal"), use_container_width=True)
        if "cpu" in system:
            st.plotly_chart(px.line(system, x="created_at", y="cpu", title="System CPU signal"), use_container_width=True)
        if "disk_usage" in system:
            st.plotly_chart(px.line(system, x="created_at", y="disk_usage", title="Storage summary signal"), use_container_width=True)
    launches = frames["launches"]
    if not launches.empty:
        st.subheader("Application launch observations")
        st.dataframe(launches, use_container_width=True, hide_index=True)
    anomalies = detect_anomalies()
    if anomalies:
        st.subheader("Unusual behavior")
        for item in anomalies:
            st.warning(item["message"])
    else:
        st.caption("No anomalies detected from available usage samples.")
    samples = list_usage(limit=50)
    if samples:
        st.subheader("Recent samples")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "When": s.created_at,
                        "Type": s.subject_type,
                        "Name": s.display_name,
                        "CPU": s.cpu,
                        "Memory": s.memory,
                        "Disk": s.disk_usage,
                    }
                    for s in samples
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )


def render_system_explorer(snap: Snapshot, rows: list[Any]) -> None:
    page_header(
        "System Explorer",
        "Unified connected explorer: applications ↔ processes ↔ startup ↔ projects ↔ environments ↔ ports ↔ knowledge.",
    )
    query = st.text_input("Start from (name/path)", value="Cursor", key="explorer_q")
    graph = build_explorer_graph(snap.id, rows, root_query=query, max_depth=3)
    if not graph:
        st.warning("No matching root item in the current snapshot.")
        return
    st.subheader(" → ".join(graph.path_labels[:10]))
    metrics_row({"Nodes": len(graph.nodes), "Edges": len(graph.edges), "Root": graph.root.name})
    st.dataframe(pd.DataFrame(explorer_table(graph)), use_container_width=True, hide_index=True)
    with st.expander("Nodes"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Name": n.name,
                        "Category": n.category,
                        "Path": n.path,
                        "Summary": n.summary,
                        "Project": n.meta.get("project_key"),
                        "Knowledge": n.meta.get("knowledge_key"),
                    }
                    for n in graph.nodes
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )


def render_search_v4(snap: Snapshot, rows: list[Any]) -> None:
    page_header("Search", "Natural-language inventory search grounded entirely in local data.")
    q = st.text_input(
        "Query",
        placeholder="What uses Docker? Which projects use Python? Show inactive applications…",
        key="search_v4_q",
    )
    c1, c2 = st.columns(2)
    save_name = c1.text_input("Save search as", key="search_save_name")
    if c2.button("Save search") and save_name and q:
        save_search(save_name, q)
        st.success("Saved")
    saved = list_saved_searches()
    if saved:
        pick = st.selectbox("Saved searches", ["—"] + [f"{n}: {v}" for n, v in saved], key="saved_search_pick")
        if pick != "—":
            q = pick.split(": ", 1)[-1]
    if not q:
        st.info("Enter a query to search the current snapshot.")
        return
    hits = search_inventory(q, rows)
    metrics_row({"Matches": len(hits)})
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Category": h.category,
                    "Name": h.name,
                    "Path": h.path,
                    "Project": getattr(h, "project_key", None),
                    "Disk": format_bytes(h.disk_usage) if h.disk_usage else "—",
                    "Running": h.running_state,
                }
                for h in hits[:300]
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )


def render_assistant_v4(snap: Snapshot | None, rows: list[Any]) -> None:
    page_header("Assistant", "Answers only from collected evidence. Never invents facts.")
    q = st.text_input("Ask about your Mac inventory", key="assistant_v4_q")
    if not q:
        st.info("Examples: What is using memory? Can I uninstall Docker? What changed yesterday?")
        return
    answer = answer_question_detailed(q, rows or [])
    st.markdown(answer.as_markdown())


def render_developer_dashboard(snap: Snapshot, rows: list[Any]) -> None:
    page_header("Developer Dashboard", "Projects, repositories, containers, environments, ports, and workspace health.")
    workspaces = list_workspaces()
    metrics = developer_dashboard_metrics(rows, workspaces)
    metrics_row(metrics)
    dep = project_dependency_frame(rows)
    if not dep.empty:
        st.subheader("Project dependency graph (table)")
        st.dataframe(dep, use_container_width=True, hide_index=True)
        fig = px.scatter(dep, x="project", y="category", hover_name="item", title="Project dependencies")
        st.plotly_chart(fig, use_container_width=True)
    members_by_id = {w.id: list_members(w.id) for w in workspaces}
    ws_frame = workspace_map_frame(workspaces, members_by_id)
    if not ws_frame.empty:
        st.subheader("Workspace map")
        st.dataframe(ws_frame, use_container_width=True, hide_index=True)
    st.subheader("Storage treemap")
    tree = storage_treemap_frame(rows)
    if not tree.empty and {"Bucket", "Item", "Size bytes"}.issubset(set(tree.columns)):
        st.plotly_chart(
            px.treemap(tree, path=["Bucket", "Item"], values="Size bytes", title="Storage overview"),
            use_container_width=True,
        )
    elif not tree.empty:
        st.dataframe(tree, use_container_width=True, hide_index=True)


def render_automation(snap: Snapshot | None, rows: list[Any]) -> None:
    page_header("Automation", "Local rules for snapshots, reports, and threshold notifications. No cloud.")
    rules = list_rules()
    for rule in rules:
        cols = st.columns([3, 1, 1, 2])
        cols[0].write(f"**{rule.name}** (`{rule.rule_type}` / {rule.schedule})")
        enabled = cols[1].checkbox("On", value=rule.enabled, key=f"rule_en_{rule.id}")
        if enabled != rule.enabled:
            set_rule_enabled(rule.id, enabled)
        if cols[2].button("Run", key=f"rule_run_{rule.id}"):
            msg = run_rule(rule, inventory_rows=rows, force=True)
            st.info(msg)
        cols[3].caption(rule.last_result or "Never run")
    st.subheader("Recent runs")
    runs = list_runs(30)
    if runs:
        st.dataframe(
            pd.DataFrame(
                [{"When": r.created_at, "Rule": r.rule_name, "Result": r.result, "Message": r.message} for r in runs]
            ),
            use_container_width=True,
            hide_index=True,
        )


def render_visual_analytics(snap: Snapshot, rows: list[Any]) -> None:
    page_header("Visual Analytics", "Timeline, usage, relationships, and storage visualizations.")
    tab1, tab2, tab3, tab4 = st.tabs(["Timeline", "Usage", "Relationships", "Storage"])
    with tab1:
        frame = timeline_chart_frame(30)
        if frame.empty:
            st.info("No timeline chart data yet.")
        else:
            st.plotly_chart(px.bar(frame, x="date", y="count", color="event_type"), use_container_width=True)
    with tab2:
        render_usage_history(snap, rows)
    with tab3:
        rel = relationship_graph_frame(snap.id)
        if rel.empty:
            st.info("No relationships in this snapshot.")
        else:
            st.dataframe(rel, use_container_width=True, hide_index=True)
    with tab4:
        tree = storage_treemap_frame(rows)
        if tree.empty:
            st.info("No storage treemap data.")
        else:
            st.dataframe(tree, use_container_width=True, hide_index=True)


def render_plugins_page() -> None:
    page_header("Plugins", "Collector plugins with isolated failure domains, metadata, and integration flags.")
    manifest = plugin_manifest()
    metrics_row({"Plugins": len(manifest), "Enabled": len([p for p in manifest if p["enabled"]])})
    st.dataframe(pd.DataFrame(manifest), use_container_width=True, hide_index=True)
