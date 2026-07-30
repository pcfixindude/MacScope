from __future__ import annotations

from config import APP_VERSION, SCHEMA_VERSION
from inventory import Item
from macscope.assistant import answer_question_detailed
from macscope.automation import ensure_default_rules, list_rules, run_rule
from macscope.explorer import build_explorer_graph
from macscope.knowledge import knowledge_count, lookup_knowledge
from macscope.plugins import bootstrap_builtin_plugins, clear_registry, plugin_manifest
from macscope.projects import Project, enrich_project_intelligence, project_inventory_summary
from macscope.recommendations import build_recommendations
from macscope.search import search_inventory
from macscope.timeline import export_timeline_csv, record_timeline, timeline_for_period
from macscope.usage import record_usage_from_snapshot, usage_series
from macscope.workspaces import add_member, create_workspace, list_members, start_workspace, stop_workspace, workspace_status
from snapshot import get_relationships, save_snapshot


def test_version_and_schema_v4():
    assert APP_VERSION == "4.0.0"
    assert SCHEMA_VERSION == 4
    assert open("VERSION", encoding="utf-8").read().strip() == "4.0.0"


def test_knowledge_pack_thousands():
    assert knowledge_count() >= 2000
    entry = lookup_knowledge(name="Docker Desktop")
    assert entry is not None
    assert entry.developer


def test_project_intelligence(tmp_path):
    (tmp_path / "requirements.txt").write_text("streamlit\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("import streamlit\n", encoding="utf-8")
    project = Project(key=str(tmp_path), name=tmp_path.name, path=str(tmp_path), indicators=["Python"])
    enrich_project_intelligence(project)
    assert project.readme
    assert project.requirements
    assert "requirements.txt" in project.package_files


def test_workspace_lifecycle():
    ws = create_workspace("Demo Workspace", "test")
    add_member(ws.id, "url", "Docs", "https://example.com")
    add_member(ws.id, "project", "Proj", "/tmp")
    members = list_members(ws.id)
    assert len(members) == 2
    status = workspace_status(ws.id, [])
    assert status.members == 2
    logs = start_workspace(ws.id)
    assert logs
    logs = stop_workspace(ws.id)
    assert logs


def test_recommendations_explain_why():
    items = [
        Item(
            category="Applications",
            name="UnusedApp",
            path="/Applications/UnusedApp.app",
            running_state="Not running",
            disk_usage=2 * 1024**3,
            risk="Caution",
        )
    ]
    items[0].ensure_stable_id()
    recs = build_recommendations(items)
    assert recs
    assert any("not an automatic delete" in r.why.lower() or "review" in r.recommended_action.lower() for r in recs)


def test_search_v2_queries():
    rows = [
        Item(category="Projects", name="demo", path="/tmp/demo", subtype="Python,Docker", project_key="/tmp/demo"),
        Item(category="Docker", name="demo-api", item_type="Container", status="running"),
        Item(category="Applications", name="IdleApp", running_state="Not running"),
        Item(category="AI", name="old-model.gguf", risk="Caution"),
    ]
    for r in rows:
        r.ensure_stable_id()
    assert search_inventory("which projects use Python", rows)
    assert search_inventory("what uses Docker", rows)
    assert search_inventory("show inactive applications", rows)
    assert search_inventory("which AI models are unused", rows)


def test_assistant_evidence_and_confidence():
    rows = [
        Item(category="Processes", name="Python", memory=12.5, pid=123, cpu=1.0),
    ]
    rows[0].ensure_stable_id()
    answer = answer_question_detailed("What is using memory?", rows)
    assert answer.confidence > 0
    assert answer.evidence
    assert "Python" in answer.text
    empty = answer_question_detailed("totally unknown xyzzy fact?", [])
    assert "will not invent" in empty.text.lower() or empty.confidence == 0


def test_usage_and_timeline_export():
    items = [
        Item(category="Processes", name="Finder", memory=1.0, cpu=0.2),
        Item(category="Applications", name="Finder", running_state="Running", disk_usage=100),
        Item(category="Projects", name="demo", path="/tmp/demo", project_key="/tmp/demo", disk_usage=10),
    ]
    for i in items:
        i.ensure_stable_id()
    sid = save_snapshot(items, note="v4 usage")
    assert record_usage_from_snapshot(sid, items) > 0
    assert usage_series("system", "host", days=30) is not None
    record_timeline("project_activity", "Branch touch", category="Projects", snapshot_id=sid)
    events = timeline_for_period("weekly")
    assert events
    csv_text = export_timeline_csv(events)
    assert "event_type" in csv_text


def test_plugins_and_explorer():
    clear_registry()
    bootstrap_builtin_plugins()
    manifest = plugin_manifest()
    assert len(manifest) >= 10
    items = [
        Item(category="Applications", name="Cursor", path="/Applications/Cursor.app"),
        Item(category="Processes", name="Cursor", path="/Applications/Cursor.app/Contents/MacOS/Cursor", related_application="Cursor"),
        Item(category="Projects", name="MacScope", path="/Users/test/Projects/MacScope", project_key="/Users/test/Projects/MacScope", subtype="Python,Git"),
        Item(category="Python", name="venv", path="/Users/test/Projects/MacScope/.venv", project_key="/Users/test/Projects/MacScope", subtype="venv"),
    ]
    for i in items:
        i.ensure_stable_id()
    # Link process to app via relationships builder path through snapshot
    from macscope.relationships import build_relationships
    from macscope.projects import link_inventory_to_projects

    projects = [
        Project(
            key="/Users/test/Projects/MacScope",
            name="MacScope",
            path="/Users/test/Projects/MacScope",
            indicators=["Python", "Git"],
            stable_id=items[2].stable_id,
        )
    ]
    rels = build_relationships(items) + link_inventory_to_projects(items, projects)
    sid = save_snapshot(items, relationships=rels)
    assert get_relationships(sid)
    # Use ORM rows for explorer
    from snapshot import get_snapshot

    _, rows = get_snapshot(sid)
    graph = build_explorer_graph(sid, rows, root_query="Cursor", max_depth=2)
    assert graph is not None
    assert graph.nodes


def test_automation_defaults():
    ensure_default_rules()
    rules = list_rules()
    assert len(rules) >= 6
    msg = run_rule(rules[0], force=True)
    assert isinstance(msg, str)


def test_project_inventory_summary():
    items = [
        Item(category="Projects", name="demo", path="/tmp/demo", project_key="/tmp/demo"),
        Item(category="Python", name="venv", path="/tmp/demo/.venv", project_key="/tmp/demo", subtype="venv"),
        Item(category="Network", name="app", network_ports="127.0.0.1:8501", project_key="/tmp/demo"),
    ]
    buckets = project_inventory_summary(items, "/tmp/demo")
    assert buckets["virtual_environments"]
    assert buckets["ports"]
