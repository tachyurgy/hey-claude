"""Sound event wiring — including the `endpoint` ('stopped listening') cue."""

from dataclasses import fields

from hey_claude import sounds
from hey_claude.cli import _SOUND_EVENTS
from hey_claude.config import Config

EVENTS = ("wake", "endpoint", "dispatch", "cancel", "error")


def test_endpoint_has_a_default_sound():
    assert "endpoint" in sounds.DEFAULTS
    assert sounds.resolve("endpoint") == sounds.DEFAULTS["endpoint"]
    # Default is the bundled custom earcon (falls back to a system sound only if
    # the packaged .wav is missing).
    default = sounds.DEFAULTS["endpoint"]
    assert default.name in ("endpoint.wav", "Pop.aiff")
    assert default.exists()


def test_every_event_resolves_and_is_overridable():
    for ev in EVENTS:
        assert sounds.resolve(ev) is not None        # built-in default
        assert sounds.resolve(ev, "none") is None     # silenceable
        assert sounds.resolve(ev, "Morse").name == "Morse.aiff"  # by system name


def test_event_map_matches_config_fields_and_defaults():
    # The three sources of truth must agree, or a config set won't reach playback.
    cfg_fields = {f.name for f in fields(Config)}
    for ev in EVENTS:
        assert ev in _SOUND_EVENTS, f"{ev} missing from CLI event map"
        field_name = _SOUND_EVENTS[ev][0]
        assert field_name == f"sound_{ev}"
        assert field_name in cfg_fields, f"{field_name} not a Config field"
        assert ev in sounds.DEFAULTS, f"{ev} missing a default sound"
