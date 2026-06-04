"""Agent presets: switching the launched agent via config."""

from hey_claude import agents
from hey_claude.config import Config


def test_default_preset_is_claude_bg():
    assert agents.DEFAULT == "claude-bg"
    assert agents.get("claude-bg") is not None
    assert agents.get("nope") is None


def test_external_preset_has_command_placeholder():
    for key in ("codex", "aider", "opencode", "gemini"):
        p = agents.get(key)
        assert p is not None
        assert "{command}" in p.template


def test_describe_active_recognizes_builtin_and_template():
    assert agents.describe_active("", "bg") == "claude-bg"
    assert agents.describe_active("", "terminal") == "claude-terminal"
    assert agents.describe_active("codex exec {command}", "bg") == "codex"
    assert agents.describe_active("my-agent {command}", "bg").startswith("custom")


def test_claude_builtin_clears_template():
    cfg = Config()
    cfg.launch_template = "codex exec {command}"
    p = agents.get("claude-bg")
    cfg.launch_template = p.template
    cfg.launch_mode = p.launch_mode
    assert cfg.launch_template == ""
    assert cfg.launch_mode == "bg"


def test_validate_template_requires_command_placeholder():
    assert agents.validate_template("codex exec {command}") is None
    assert agents.validate_template("") is not None        # empty
    assert agents.validate_template("codex exec") is not None  # no {command}
    assert "{command}" in agents.validate_template("foo bar")
