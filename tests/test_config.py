"""Config: round-trip persistence and typed coercion of CLI values."""

import os

import pytest

from hey_claude.config import Config


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HEY_CLAUDE_HOME", str(tmp_path / "hc"))
    return tmp_path


def test_save_load_roundtrip(home):
    cfg = Config()
    cfg.threshold = 0.7
    cfg.wake_phrase = "hey claude"
    cfg.launch_template = 'claude --bg --name {name} {command}'
    cfg.chime = False
    cfg.max_concurrent = 3
    cfg.save()

    loaded = Config.load()
    assert loaded.threshold == 0.7
    assert loaded.launch_template == 'claude --bg --name {name} {command}'
    assert loaded.chime is False
    assert loaded.max_concurrent == 3


def test_load_defaults_when_absent(home):
    cfg = Config.load()
    assert cfg.engine == "openwakeword"
    assert cfg.launch_mode == "bg"


def test_set_field_coercion(home):
    cfg = Config()
    cfg.set_field("threshold", "0.42")
    cfg.set_field("chime", "false")
    cfg.set_field("max_concurrent", "5")
    cfg.set_field("wake_phrase", "computer")
    assert cfg.threshold == 0.42 and isinstance(cfg.threshold, float)
    assert cfg.chime is False
    assert cfg.max_concurrent == 5 and isinstance(cfg.max_concurrent, int)
    assert cfg.wake_phrase == "computer"


def test_set_unknown_field_raises(home):
    with pytest.raises(KeyError):
        Config().set_field("not_a_real_key", "x")


def test_toml_escapes_quotes(home):
    cfg = Config()
    cfg.launch_template = 'echo "hi" {command}'
    cfg.save()
    assert Config.load().launch_template == 'echo "hi" {command}'
