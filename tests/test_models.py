"""The wake-word models bundled as package data must be present and resolvable."""

from pathlib import Path

import pytest

from hey_claude import config
from hey_claude.models import CATALOG, DEFAULT, available, bundled_path


def test_default_is_catalogued():
    assert DEFAULT == "hey_claude"
    assert DEFAULT in CATALOG


def test_bundled_default_ships_on_disk():
    p = bundled_path("hey_claude")
    assert p is not None and p.exists() and p.suffix == ".onnx"


def test_available_lists_present_models():
    names = available()
    assert "hey_claude" in names
    # every advertised model is actually on disk
    for n in names:
        assert (bundled_path(n) or Path("/nonexistent")).exists()


def test_resolve_empty_falls_back_to_bundled(monkeypatch, tmp_path):
    # No installed model in a fresh HOME => resolves to the bundled default.
    monkeypatch.setenv("HEY_CLAUDE_HOME", str(tmp_path))
    p = config.resolve_wakeword("")
    assert p.exists() and p.name == "hey_claude.onnx"


def test_resolve_bundled_name(tmp_path, monkeypatch):
    monkeypatch.setenv("HEY_CLAUDE_HOME", str(tmp_path))
    p = config.resolve_wakeword("okay_claude")
    assert p.exists() and p.name == "okay_claude.onnx"


def test_resolve_explicit_path_is_honored(tmp_path, monkeypatch):
    monkeypatch.setenv("HEY_CLAUDE_HOME", str(tmp_path))
    fake = tmp_path / "custom.onnx"
    fake.write_bytes(b"x")
    assert config.resolve_wakeword(str(fake)) == fake
