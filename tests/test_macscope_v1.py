from __future__ import annotations

import os
import plistlib
from pathlib import Path
from unittest.mock import patch

import pytest

from actions import (
    ActionError,
    brew_cmd,
    disable_launch_agent,
    force_quit_process,
    move_app_to_trash,
    stop_process,
    unload_launch_item,
)
from compare import compare_snapshots
from identifier import (
    CLASS_APPLE,
    CLASS_ORPHANED,
    CLASS_THIRD_PARTY,
    CLASS_USER,
    classify_item,
)
from inventory import Item
from models import InventoryItem
from protection import (
    is_protected_path,
    is_protected_process,
    validate_app_bundle_target,
    validate_launch_plist_target,
)
from utils import parse_program_from_plist, read_plist, unique_trash_destination


# ---------------------------------------------------------------------------
# Protected paths
# ---------------------------------------------------------------------------


def test_protected_system_paths():
    assert is_protected_path("/System/Library/CoreServices/Finder.app")
    assert is_protected_path("/usr/bin/python3")
    assert is_protected_path("/bin/zsh")
    assert is_protected_path("/sbin/launchd")
    assert not is_protected_path("/Applications/Safari.app")
    assert not is_protected_path(str(Path.home() / "Library/LaunchAgents/com.example.plist"))
    assert not is_protected_path(None)


# ---------------------------------------------------------------------------
# Apple-item classification
# ---------------------------------------------------------------------------


def test_apple_item_classification():
    item = Item(
        category="Startup",
        name="com.apple.example",
        path="/System/Library/LaunchAgents/com.apple.example.plist",
        label="com.apple.example",
        executable_path="/usr/libexec/example",
        protected=True,
    )
    classify_item(item)
    assert item.classification == CLASS_APPLE
    assert item.protected is True
    assert "Management actions are disabled" in (item.explanation or "")


def test_third_party_homebrew_classification():
    item = Item(
        category="Homebrew",
        name="wget",
        vendor="Formula",
        installation_source="Homebrew",
        item_type="Formula",
    )
    classify_item(item)
    assert item.classification == CLASS_THIRD_PARTY


def test_user_launch_agent_classification(tmp_path, monkeypatch):
    home = tmp_path / "home"
    agents = home / "Library" / "LaunchAgents"
    agents.mkdir(parents=True)
    exe = tmp_path / "myscript"
    exe.write_text("#!/bin/sh\n")
    monkeypatch.setattr("identifier.Path.home", lambda: home)
    item = Item(
        category="Startup",
        name="com.user.streamlit",
        path=str(agents / "com.user.streamlit.plist"),
        label="com.user.streamlit",
        executable_path=str(exe),
        related_application="Streamlit",
    )
    classify_item(item)
    assert item.classification == CLASS_USER
    assert "Streamlit" in (item.explanation or "")


# ---------------------------------------------------------------------------
# Plist parsing
# ---------------------------------------------------------------------------


def test_plist_parsing(tmp_path):
    plist = tmp_path / "com.example.helper.plist"
    data = {
        "Label": "com.example.helper",
        "ProgramArguments": ["/usr/local/bin/helper", "--flag"],
        "RunAtLoad": True,
    }
    with plist.open("wb") as handle:
        plistlib.dump(data, handle)
    loaded = read_plist(plist)
    assert loaded["Label"] == "com.example.helper"
    assert parse_program_from_plist(loaded) == "/usr/local/bin/helper"
    assert parse_program_from_plist({"Program": "/bin/echo"}) == "/bin/echo"
    assert parse_program_from_plist({}) is None


# ---------------------------------------------------------------------------
# Missing executable / orphan detection
# ---------------------------------------------------------------------------


def test_orphan_detection():
    item = Item(
        category="Startup",
        name="com.example.missing",
        path=str(Path.home() / "Library/LaunchAgents/com.example.missing.plist"),
        label="com.example.missing",
        executable_path="/tmp/macscope-definitely-missing-executable-xyz",
        details={"program": "/tmp/macscope-definitely-missing-executable-xyz"},
    )
    classify_item(item)
    assert item.classification == CLASS_ORPHANED
    assert "does not exist" in (item.explanation or "")


# ---------------------------------------------------------------------------
# Snapshot comparison
# ---------------------------------------------------------------------------


def _row(**kwargs) -> InventoryItem:
    defaults = dict(
        snapshot_id=1,
        category="Applications",
        name="Demo",
        path="/Applications/Demo.app",
        status="Installed",
        vendor=None,
        version="1.0",
        cpu=None,
        memory=None,
        risk="Safe",
        protected=False,
        details_json="{}",
        label="com.demo.app",
        item_type="Application",
        executable_path="/Applications/Demo.app/Contents/MacOS/Demo",
        publisher=None,
        installation_source=None,
        running_state="Not running",
        startup_state=None,
        network_ports=None,
        classification="Known third-party",
        explanation=None,
        related_application=None,
        available_actions="[]",
    )
    defaults.update(kwargs)
    return InventoryItem(**defaults)


def test_snapshot_comparison():
    older = [
        _row(name="Keep", version="1.0"),
        _row(name="Gone", path="/Applications/Gone.app", label="com.gone"),
        _row(
            category="Processes",
            name="oldproc",
            path="/usr/local/bin/oldproc",
            executable_path="/usr/local/bin/oldproc",
            status="Running",
            running_state="Running",
            label=None,
            details_json='{"command":"oldproc"}',
        ),
    ]
    newer = [
        _row(name="Keep", version="2.0"),
        _row(name="NewApp", path="/Applications/NewApp.app", label="com.new"),
        _row(
            category="Processes",
            name="newproc",
            path="/usr/local/bin/newproc",
            executable_path="/usr/local/bin/newproc",
            status="Running",
            running_state="Running",
            label=None,
            details_json='{"command":"newproc"}',
        ),
        _row(
            category="Network",
            name="nginx",
            label="127.0.0.1:8080",
            network_ports="127.0.0.1:8080",
            status="Listening",
            path=None,
            details_json='{"address":"127.0.0.1:8080","pid":99}',
        ),
        _row(
            category="Startup",
            name="com.user.newagent",
            path=str(Path.home() / "Library/LaunchAgents/com.user.newagent.plist"),
            label="com.user.newagent",
            startup_state="enabled",
            status="Configured",
        ),
        _row(
            category="Services",
            name="mysql",
            status="started",
            label="mysql",
            path=None,
        ),
    ]
    # Add older mysql stopped for service change detection via shared identity
    older.append(
        _row(
            category="Services",
            name="mysql",
            status="stopped",
            label="mysql",
            path=None,
        )
    )
    result = compare_snapshots(older, newer)
    assert any(e["Name"] == "NewApp" for e in result.added)
    assert any(e["Name"] == "Gone" for e in result.removed)
    assert any(e["Name"] == "Keep" for e in result.changed)
    assert any(e["Name"] == "Keep" for e in result.version_changes)
    assert any(e["Name"] == "newproc" for e in result.newly_running)
    assert any(e["Name"] == "com.user.newagent" for e in result.newly_enabled_startup)
    assert any(e.get("Ports") == "127.0.0.1:8080" or e.get("Label") == "127.0.0.1:8080" for e in result.newly_opened_ports)
    assert any(e["Name"] == "mysql" for e in result.service_status_changes)


# ---------------------------------------------------------------------------
# Action target validation
# ---------------------------------------------------------------------------


def test_launch_agent_validation(tmp_path, monkeypatch):
    home = tmp_path / "home"
    agents = home / "Library" / "LaunchAgents"
    agents.mkdir(parents=True)
    plist = agents / "com.example.ok.plist"
    plist.write_bytes(plistlib.dumps({"Label": "com.example.ok", "Program": "/bin/echo"}))
    monkeypatch.setattr("protection.Path.home", lambda: home)

    ok, reason, resolved = validate_launch_plist_target(plist)
    assert ok is True
    assert resolved == plist.resolve()

    ok, reason, _ = validate_launch_plist_target("/System/Library/LaunchAgents/com.apple.x.plist")
    assert ok is False

    ok, reason, _ = validate_launch_plist_target("/Library/LaunchDaemons/com.third.plist")
    assert ok is False
    assert "administrator" in reason.lower() or "Version 1" in reason


def test_app_bundle_validation():
    ok, reason, _ = validate_app_bundle_target("/System/Applications/Safari.app")
    assert ok is False
    assert reason


# ---------------------------------------------------------------------------
# Process-stop protection
# ---------------------------------------------------------------------------


def test_process_stop_protection():
    blocked, reason = is_protected_process(pid=1, name="launchd")
    assert blocked is True
    blocked, reason = is_protected_process(pid=os.getpid())
    assert blocked is True
    blocked, reason = is_protected_process(pid=os.getppid())
    assert blocked is True
    blocked, reason = is_protected_process(pid=999999, name="WindowServer")
    assert blocked is True
    blocked, reason = is_protected_process(pid=999999, name="MyApp", exe="/Applications/MyApp.app/Contents/MacOS/MyApp")
    assert blocked is False


def test_stop_process_blocked(monkeypatch):
    with patch("actions.os.kill") as kill_mock:
        with pytest.raises(ActionError):
            stop_process(1, name="launchd")
        kill_mock.assert_not_called()


def test_force_quit_blocked_for_self():
    with patch("actions.os.kill") as kill_mock:
        with pytest.raises(ActionError):
            force_quit_process(os.getpid())
        kill_mock.assert_not_called()


# ---------------------------------------------------------------------------
# LaunchAgent backup and disable logic
# ---------------------------------------------------------------------------


def test_launch_agent_backup_and_disable(tmp_path, monkeypatch):
    home = tmp_path / "home"
    agents = home / "Library" / "LaunchAgents"
    agents.mkdir(parents=True)
    plist = agents / "com.example.agent.plist"
    plist.write_bytes(
        plistlib.dumps(
            {
                "Label": "com.example.agent",
                "ProgramArguments": ["/bin/echo", "hi"],
                "RunAtLoad": True,
            }
        )
    )
    backups = tmp_path / "backups"
    backups.mkdir()
    monkeypatch.setattr("protection.Path.home", lambda: home)
    monkeypatch.setattr("actions.BACKUPS_DIR", backups)
    monkeypatch.setattr("macscope.backup.BACKUPS_DIR", backups)
    monkeypatch.setattr("actions.unload_launch_item", lambda path: None)
    monkeypatch.setattr("actions._record", lambda *a, **k: None)
    monkeypatch.setattr("macscope.backup.SessionLocal", __import__("database").SessionLocal)

    with patch("actions.run_command", return_value=(0, "", "")):
        disabled = disable_launch_agent(str(plist))
    assert disabled.exists()
    assert disabled.name.endswith(".plist.disabled")
    assert not plist.exists()
    assert list(backups.rglob("com.example.agent*"))


def test_unload_launch_item_mocked(tmp_path, monkeypatch):
    home = tmp_path / "home"
    agents = home / "Library" / "LaunchAgents"
    agents.mkdir(parents=True)
    plist = agents / "com.example.agent.plist"
    plist.write_bytes(plistlib.dumps({"Label": "com.example.agent", "Program": "/bin/echo"}))
    monkeypatch.setattr("protection.Path.home", lambda: home)
    monkeypatch.setattr("actions._record", lambda *a, **k: None)
    with patch("actions.run_command", return_value=(0, "ok", "")) as run:
        unload_launch_item(str(plist))
        assert run.call_args[0][0][0] == "launchctl"
        assert run.call_args[0][0][1] == "bootout"


# ---------------------------------------------------------------------------
# Trash destination collision handling
# ---------------------------------------------------------------------------


def test_trash_destination_collision(tmp_path):
    trash = tmp_path / ".Trash"
    trash.mkdir()
    (trash / "Demo.app").mkdir()
    dest = unique_trash_destination(trash, "Demo.app")
    assert dest.name == "Demo 1.app"
    (trash / "Demo 1.app").mkdir()
    dest2 = unique_trash_destination(trash, "Demo.app")
    assert dest2.name == "Demo 2.app"


def test_move_app_to_trash_collision(tmp_path, monkeypatch):
    app = tmp_path / "Widget.app"
    app.mkdir()
    trash = tmp_path / ".Trash"
    trash.mkdir()
    (trash / "Widget.app").mkdir()
    monkeypatch.setattr("actions.Path.home", lambda: tmp_path)
    monkeypatch.setattr("actions._record", lambda *a, **k: None)

    def fake_validate(path):
        return True, "", app

    monkeypatch.setattr("actions.validate_app_bundle_target", fake_validate)
    dest = move_app_to_trash(str(app))
    assert dest.name == "Widget 1.app"
    assert dest.exists()
    assert not app.exists()


# ---------------------------------------------------------------------------
# Homebrew command construction
# ---------------------------------------------------------------------------


def test_homebrew_command_construction(monkeypatch):
    monkeypatch.setattr("actions.shutil.which", lambda name: "/opt/homebrew/bin/brew")
    assert brew_cmd("services", "stop", "mysql") == [
        "/opt/homebrew/bin/brew",
        "services",
        "stop",
        "mysql",
    ]
    assert brew_cmd("uninstall", "--cask", "docker") == [
        "/opt/homebrew/bin/brew",
        "uninstall",
        "--cask",
        "docker",
    ]


def test_homebrew_missing(monkeypatch):
    monkeypatch.setattr("actions.shutil.which", lambda name: None)
    with pytest.raises(ActionError):
        brew_cmd("list")


# ---------------------------------------------------------------------------
# Analyzer smoke
# ---------------------------------------------------------------------------


def test_health_score_range():
    from analyzer import health_score

    score, notes = health_score([Item("Applications", "Test", risk="Safe")])
    assert 0 <= score <= 100
    assert isinstance(notes, list)
