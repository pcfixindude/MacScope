from __future__ import annotations

import json
import plistlib
from pathlib import Path
from unittest.mock import patch

import pytest

from compare import compare_snapshots
from database import get_schema_version, init_db
from identifier import classify_item
from inventory import Item
from macscope.catalog import lookup_catalog
from macscope.collectors.network import classify_binding
from macscope.redaction import redact_command, redact_text
from macscope.relationships import build_relationships
from macscope.settings import Settings, load_settings, save_settings
from macscope.stable_id import item_stable_id, stable_id
from models import InventoryItem
from protection import is_protected_path
from snapshot import row_identity_key, save_snapshot
from utils import read_plist


def test_stable_id_deterministic():
    a = stable_id("Applications", "com.demo", "/Applications/Demo.app")
    b = stable_id("Applications", "com.demo", "/Applications/Demo.app")
    c = stable_id("Applications", "com.other", "/Applications/Other.app")
    assert a == b
    assert a != c
    assert item_stable_id(category="Applications", name="Demo", path="/Applications/Demo.app").startswith("applications:")


def test_schema_version():
    init_db()
    assert get_schema_version() >= 2


def test_network_binding_classification():
    assert classify_binding("127.0.0.1") == "local_only"
    assert classify_binding("0.0.0.0") == "public_interface"
    assert classify_binding("192.168.1.10") == "local_network_reachable"


def test_catalog_lookup():
    entry = lookup_catalog(bundle_id="com.docker.helper", label="com.docker.vmnetd")
    assert entry is not None
    assert "Docker" in entry.display_name


def test_relationships_generation():
    app = Item(category="Applications", name="Demo", path="/Applications/Demo.app", bundle_id="com.demo.app")
    proc = Item(
        category="Processes",
        name="Demo",
        path="/Applications/Demo.app/Contents/MacOS/Demo",
        executable_path="/Applications/Demo.app/Contents/MacOS/Demo",
        related_application="Demo",
        pid=4242,
    )
    port = Item(category="Network", name="Demo", network_ports="127.0.0.1:8501", pid=4242, label="127.0.0.1:8501")
    for item in (app, proc, port):
        classify_item(item)
    rels = build_relationships([app, proc, port])
    types = {r.relation_type for r in rels}
    assert "application_owns_process" in types
    assert "process_opens_port" in types


def test_redaction(monkeypatch):
    settings = Settings(redact_username=True, redact_home_path=True, redact_command_args=True)
    monkeypatch.setattr("macscope.redaction.load_settings", lambda: settings)
    home = str(Path.home())
    text = redact_text(f"{home}/Projects/secret", settings)
    assert home not in text
    cmd = redact_command("tool --password supersecret --token abc", settings)
    assert "supersecret" not in cmd
    assert "<redacted>" in cmd or "password" in cmd.lower()


def test_settings_persistence(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setattr("macscope.settings.SETTINGS_PATH", path)
    monkeypatch.setattr("config.SETTINGS_PATH", path)
    s = Settings(theme="dark", enable_destructive_actions=False)
    save_settings(s)
    loaded = load_settings()
    assert loaded.theme == "dark"
    assert loaded.enable_destructive_actions is False
    assert loaded.destructive_allowed() is False


def test_snapshot_save_and_identity():
    items = [
        Item(category="Applications", name="Demo", path="/Applications/Demo.app", bundle_id="com.demo"),
        Item(category="Network", name="nginx", network_ports="127.0.0.1:80", label="127.0.0.1:80", details={"address": "127.0.0.1:80"}),
    ]
    for item in items:
        classify_item(item)
    sid = save_snapshot(items, note="test")
    assert sid >= 1
    from snapshot import get_snapshot

    snap, rows = get_snapshot(sid)
    assert snap is not None
    assert len(rows) == 2
    assert all(row.stable_id for row in rows)
    keys = {row_identity_key(r) for r in rows}
    assert len(keys) == 2


def test_ai_model_suffix_and_cleanup():
    from macscope.cleanup import find_cleanup_candidates
    from macscope.collectors.ai_models import MODEL_SUFFIXES

    assert ".gguf" in MODEL_SUFFIXES
    items = [
        Item(
            category="Startup",
            name="orphan",
            path="/tmp/x.plist",
            classification="Orphaned",
            risk="Orphaned",
            orphan_status=True,
            explanation="missing",
        ),
        Item(category="Node", name="mods", path="/tmp/proj/node_modules", subtype="node_modules", disk_usage=1000),
    ]
    for item in items:
        item.ensure_stable_id()
    cands = find_cleanup_candidates(items)
    assert any(c.candidate_type.startswith("Orphaned") for c in cands)
    assert any(c.candidate_type == "node_modules folder" for c in cands)


def test_docker_prune_preview_mocked(monkeypatch):
    from actions import docker_prune_preview

    monkeypatch.setattr("actions.shutil.which", lambda name: "/usr/local/bin/docker" if name == "docker" else None)

    def fake_run(args, timeout=20, env=None):
        return 0, json.dumps({"Type": "Images", "Reclaimable": "1.2GB", "Size": "3GB"}), ""

    monkeypatch.setattr("actions.run_command", fake_run)
    monkeypatch.setattr("actions._record", lambda *a, **k: None)
    preview = docker_prune_preview()
    assert isinstance(preview, dict)
    assert "images" in preview


def test_report_redaction_export(tmp_path, monkeypatch):
    from macscope.reports import export_markdown_summary

    monkeypatch.setattr("macscope.reports._out_dir", lambda: tmp_path)
    path = export_markdown_summary(
        {"id": 1, "created_at": "now", "hostname": "secret-host"},
        {"Applications": 1},
        [{"created_at": "t", "action": "stop", "target": "x", "result": "success"}],
    )
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "MacScope Report" in text


def test_plist_and_codesign_helpers(tmp_path):
    plist = tmp_path / "a.plist"
    with plist.open("wb") as handle:
        plistlib.dump({"Label": "com.example", "Program": "/bin/echo"}, handle)
    data = read_plist(plist)
    assert data["Label"] == "com.example"


def test_compare_uses_stable_ids():
    older = [
        InventoryItem(
            snapshot_id=1,
            category="Applications",
            name="Demo",
            path="/Applications/Demo.app",
            status="Installed",
            risk="Safe",
            protected=False,
            details_json="{}",
            stable_id="applications:demo",
            version="1.0",
            label="com.demo",
        )
    ]
    newer = [
        InventoryItem(
            snapshot_id=2,
            category="Applications",
            name="Demo",
            path="/Applications/Demo.app",
            status="Installed",
            risk="Safe",
            protected=False,
            details_json="{}",
            stable_id="applications:demo",
            version="2.0",
            label="com.demo",
        )
    ]
    result = compare_snapshots(older, newer)
    assert any(e["Name"] == "Demo" for e in result.version_changes)


def test_protected_path_still_blocks_system():
    assert is_protected_path("/System/Library/CoreServices/Finder.app")
    assert not is_protected_path("/Applications/Demo.app")
