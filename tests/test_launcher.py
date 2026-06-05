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


# --- command validation gate ----------------------------------------------

def _fake_proc(stdout="", returncode=0):
    class P:
        pass
    p = P()
    p.stdout = stdout
    p.stderr = ""
    p.returncode = returncode
    return p


def test_precheck_rejects_when_model_says_no(monkeypatch):
    import hey_claude.launcher as L
    monkeypatch.setattr(L, "resolve_claude_bin", lambda cfg: "claude")
    monkeypatch.setattr(L.subprocess, "run", lambda *a, **k: _fake_proc("NO"))
    ok, reason = L.precheck_command(Config(), "uhh")
    assert ok is False


def test_precheck_accepts_when_model_says_yes(monkeypatch):
    import hey_claude.launcher as L
    monkeypatch.setattr(L, "resolve_claude_bin", lambda cfg: "claude")
    monkeypatch.setattr(L.subprocess, "run", lambda *a, **k: _fake_proc("YES"))
    ok, _ = L.precheck_command(Config(), "fix the failing tests")
    assert ok is True


def test_precheck_fails_open_on_error(monkeypatch):
    # A missing claude binary, timeout, or nonzero exit must NOT block dispatch.
    import hey_claude.launcher as L

    def boom(cfg):
        raise LaunchError("no claude")

    monkeypatch.setattr(L, "resolve_claude_bin", boom)
    ok, _ = L.precheck_command(Config(), "do the thing")
    assert ok is True


def test_precheck_fails_open_on_timeout(monkeypatch):
    import hey_claude.launcher as L
    monkeypatch.setattr(L, "resolve_claude_bin", lambda cfg: "claude")

    def timeout(*a, **k):
        raise L.subprocess.TimeoutExpired(cmd="claude", timeout=1)

    monkeypatch.setattr(L.subprocess, "run", timeout)
    ok, _ = L.precheck_command(Config(), "do the thing")
    assert ok is True
