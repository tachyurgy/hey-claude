"""Launcher: command construction and the no-injection guarantee."""

import pytest

from hey_claude.config import Config
from hey_claude.launcher import LaunchError, render_template, resolve_work_dir, session_name


def test_session_name_truncates_and_prefixes():
    cfg = Config(name_prefix="hey-claude")
    name = session_name(cfg, "fix the failing authentication tests in the api layer please")
    assert name.startswith("hey-claude: ")
    assert len(name) <= 60


def test_template_command_is_single_arg():
    # A spoken command containing shell metacharacters must arrive as ONE argv
    # element — never split into extra arguments.
    cfg = Config(launch_template="claude --bg {command}")
    argv = render_template(cfg, "/usr/bin/claude", "ship it; rm -rf / && echo pwned")
    assert argv == ["claude", "--bg", "ship it; rm -rf / && echo pwned"]


def test_template_placeholder_substitution():
    cfg = Config(
        launch_template="{claude_bin} --bg --name {name} --permission-mode {permission_mode} {command}",
        permission_mode="acceptEdits",
        name_prefix="hc",
    )
    argv = render_template(cfg, "/bin/claude", "run tests")
    assert argv[0] == "/bin/claude"
    assert "--permission-mode" in argv and "acceptEdits" in argv
    assert argv[-1] == "run tests"


def test_template_empty_after_expansion_raises():
    cfg = Config(launch_template="   ")
    with pytest.raises(LaunchError):
        render_template(cfg, "/bin/claude", "x")


def test_work_dir_default_is_none_meaning_current_folder():
    # Empty work_dir -> None so the subprocess inherits hey-claude's own cwd.
    assert resolve_work_dir(Config()) is None


def test_work_dir_resolves_and_expands(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "proj").mkdir()
    assert resolve_work_dir(Config(work_dir=str(tmp_path / "proj"))) == str(tmp_path / "proj")
    assert resolve_work_dir(Config(work_dir="~/proj")) == str(tmp_path / "proj")


def test_work_dir_missing_dir_raises():
    with pytest.raises(LaunchError):
        resolve_work_dir(Config(work_dir="/no/such/dir/xyz123"))
