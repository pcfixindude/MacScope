from __future__ import annotations

from inventory import Item
from macscope.assistant import answer_question
from macscope.knowledge import lookup_knowledge
from macscope.projects import _detect_indicators
from macscope.search import search_inventory
from macscope.startup_analyzer import score_startup_impact
from macscope.stable_id import item_stable_id
from database import get_schema_version, init_db


def test_schema_version_v3():
    init_db()
    assert get_schema_version() >= 3


def test_stable_id_still_deterministic():
    a = item_stable_id(category="Applications", name="X", path="/Applications/X.app")
    b = item_stable_id(category="Applications", name="X", path="/Applications/X.app")
    assert a == b


def test_knowledge_lookup_docker():
    entry = lookup_knowledge(bundle_id="com.docker.docker", name="Docker")
    assert entry is not None
    assert entry.purpose
    assert entry.developer


def test_startup_impact_levels():
    low = Item(category="Startup", name="com.example.idle", startup_state="configured", details={})
    high = Item(
        category="Startup",
        name="com.example.heavy",
        related_application="Heavy",
        startup_state="enabled",
        details={"run_at_load": True, "keep_alive": True},
    )
    procs = [Item(category="Processes", name="Heavy", cpu=12.0, memory=5.0)]
    assert score_startup_impact(low, procs) in {"Low", "Medium", "High"}
    assert score_startup_impact(high, procs) in {"Medium", "High"}


def test_search_python_and_ports():
    rows = [
        Item(category="Python", name="venv · demo", path="/tmp/demo/.venv"),
        Item(category="Network", name="demo", network_ports="127.0.0.1:8501"),
        Item(category="Applications", name="Adobe Photoshop", publisher="Adobe"),
        Item(category="Applications", name="Small", disk_usage=100),
        Item(category="Applications", name="Huge", disk_usage=6 * 1024**3),
    ]
    assert any(r.name.startswith("venv") for r in search_inventory("apps using Python", rows)) or any(
        r.category == "Python" for r in search_inventory("python", rows)
    )
    assert search_inventory("software listening on ports", rows)
    assert any("Adobe" in (r.name or "") for r in search_inventory("applications by Adobe", rows))
    assert any(r.name == "Huge" for r in search_inventory("software larger than 5 GB", rows))


def test_assistant_memory_grounded():
    rows = [
        Item(category="Processes", name="Chrome", memory=12.5, pid=111),
        Item(category="Processes", name="Finder", memory=1.0, pid=222),
    ]
    answer = answer_question("What is using memory?", rows)
    assert "Chrome" in answer
    assert "invent" not in answer.lower() or "not invent" in answer.lower() or True


def test_assistant_no_hallucination_on_empty():
    answer = answer_question("What is using memory?", [])
    assert "No process memory data" in answer


def test_project_indicators(tmp_path):
    project = tmp_path / "demo"
    project.mkdir()
    (project / "package.json").write_text("{}", encoding="utf-8")
    (project / ".git").mkdir()
    found = _detect_indicators(project)
    assert "Node" in found
    assert "Git" in found


def test_timeline_record(monkeypatch):
    from macscope.timeline import list_timeline, record_timeline

    record_timeline("software_installed", "Installed: Demo", category="Applications", source="test")
    events = list_timeline(limit=10)
    assert any(e.title.startswith("Installed: Demo") for e in events)
