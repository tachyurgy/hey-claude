"""Full-teardown (`uninstall --all`) behavior for the launchd service module.

These tests never touch the real launchd agent, config dir, or ~/Applications:
every path is redirected into a tmp dir and `launchctl` is stubbed out.
"""

from pathlib import Path

import pytest

from hey_claude import service


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Redirect the agent plist, config dir, and .app bundle into tmp_path and
    stub launchctl so purge() can run with no side effects on the real system."""
    home = tmp_path / "config" / "hey-claude"
    plist = tmp_path / "LaunchAgents" / f"{service.LABEL}.plist"
    app = tmp_path / "Applications" / "Hey Claude.app"

    monkeypatch.setenv("HEY_CLAUDE_HOME", str(home))
    monkeypatch.setattr(service, "plist_path", lambda: plist)
    monkeypatch.setattr("hey_claude.appbundle.default_dest", lambda: app)

    calls: list[tuple] = []
    monkeypatch.setattr(service, "_launchctl", lambda *a: calls.append(a))
    return {"home": home, "plist": plist, "app": app, "calls": calls}


def _populate(sandbox):
    sandbox["home"].mkdir(parents=True)
    (sandbox["home"] / "config.toml").write_text("engine = \"openwakeword\"\n")
    (sandbox["home"] / "models").mkdir()
    (sandbox["home"] / "models" / "hey_claude.onnx").write_text("x")
    sandbox["plist"].parent.mkdir(parents=True)
    sandbox["plist"].write_text("<plist/>")
    sandbox["app"].mkdir(parents=True)
    (sandbox["app"] / "Contents").mkdir()


def test_purge_removes_all_state(sandbox):
    _populate(sandbox)

    rc = service.purge(assume_yes=True)

    assert rc == 0
    assert not sandbox["home"].exists()
    assert not sandbox["plist"].exists()
    assert not sandbox["app"].exists()
    # Agent was unloaded before its plist was deleted.
    assert any(c[0] == "unload" for c in sandbox["calls"])


def test_purge_aborts_on_no(sandbox, monkeypatch):
    _populate(sandbox)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "n")

    rc = service.purge(assume_yes=False)

    assert rc == 1
    assert sandbox["home"].exists()
    assert sandbox["plist"].exists()
    assert sandbox["app"].exists()
    assert sandbox["calls"] == []  # never touched launchctl


def test_purge_nothing_to_remove(sandbox):
    # Nothing populated -> clean no-op, success.
    rc = service.purge(assume_yes=True)
    assert rc == 0
    assert sandbox["calls"] == []


def test_uninstall_only_removes_agent(sandbox):
    _populate(sandbox)

    rc = service.uninstall()

    assert rc == 0
    assert not sandbox["plist"].exists()        # agent gone
    assert sandbox["home"].exists()             # config/models untouched
    assert sandbox["app"].exists()              # .app untouched
