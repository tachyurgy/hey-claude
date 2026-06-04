"""Sound event wiring — including the `endpoint` ('stopped listening') cue
and the soundpack / rotation system."""

from dataclasses import fields

import pytest

from hey_claude import sounds
from hey_claude.cli import _SOUND_EVENTS
from hey_claude.config import Config

EVENTS = ("wake", "endpoint", "dispatch", "cancel", "error")


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HEY_CLAUDE_HOME", str(tmp_path / "hc"))
    sounds._rotation.clear()  # rotation cursors are module-global
    return tmp_path


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


# --- soundpacks ------------------------------------------------------------

def test_default_pack_is_warm_and_every_builtin_resolves():
    # "warm" is the default; every builtin pack covers all five events.
    assert Config().soundpack == "warm"
    assert "warm" in sounds.BUILTIN_PACKS
    for pack in sounds.BUILTIN_PACKS:
        assert sounds.pack_dir(pack) is not None, f"{pack} folder missing"
        for ev in EVENTS:
            snd = sounds.event_sound(ev, "", pack)
            assert snd is not None and snd.exists(), f"{pack}/{ev} did not resolve"


def test_soundpack_is_a_config_field_that_roundtrips(home):
    cfg = Config()
    cfg.soundpack = "butler"
    cfg.save()
    assert Config.load().soundpack == "butler"


def test_event_override_beats_pack(home):
    # A per-event override is the most specific intent and wins over the pack.
    assert sounds.event_sound("wake", "Morse", "clicks").name == "Morse.aiff"
    assert sounds.event_sound("wake", "none", "clicks") is None


def test_pack_wake_rotates_through_variants(home):
    files = sounds.pack_event_files("clicks", "wake")
    assert len(files) >= 2, "clicks wake should have rotation variants"
    assert files[0].stem == "wake"  # bare cue leads
    seq = [sounds.event_sound("wake", "", "clicks").name for _ in range(len(files) * 2)]
    # Round-robin: one full cycle then it repeats in the same order.
    assert seq[: len(files)] == [f.name for f in files]
    assert seq[len(files):] == seq[: len(files)]


def test_partial_pack_falls_back_to_studio_default(home, tmp_path):
    pack = sounds.user_packs_dir() / "mine"
    pack.mkdir(parents=True)
    # Only provide wake; the rest must fall back so a partial pack still chimes.
    (pack / "wake.wav").write_bytes((sounds.event_sound("wake", "", "clicks")).read_bytes())
    assert sounds.event_sound("wake", "", "mine").parent.name == "mine"
    assert sounds.event_sound("dispatch", "", "mine") == sounds.DEFAULTS["dispatch"]


def test_user_pack_is_discovered_and_can_shadow_builtin(home):
    root = sounds.user_packs_dir()
    (root / "mine").mkdir(parents=True)
    (root / "clicks").mkdir(parents=True)  # same name as a builtin
    packs = sounds.list_packs()
    assert "mine" in packs and packs["mine"][0] == "custom"
    assert packs["clicks"][0] == "custom"  # user dir shadows the builtin
    assert sounds.pack_dir("clicks") == root / "clicks"
