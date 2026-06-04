"""Non-blocking audible feedback via macOS ``afplay`` and system sounds.

Audible cues matter for a voice tool: you need to know the wake word registered
*before* you start speaking the command, and that a dispatch actually happened.
All playback is fire-and-forget so it never stalls the listen loop.
"""

from __future__ import annotations

import random
import subprocess
from pathlib import Path
from typing import Optional

_SOUNDS = Path("/System/Library/Sounds")

# Audio file extensions we recognize inside a soundpack folder (afplay handles
# all of these). Order is the tie-break preference when several variants of one
# event share a stem.
_AUDIO_EXTS = (".wav", ".aiff", ".aif", ".caf", ".mp3", ".m4a", ".aac", ".flac")

# Custom earcons synthesized for hey-claude (see scripts/gen_earcons.py), bundled
# as package data so the tool sounds like a deliberate product, not a pile of
# macOS system beeps. We fall back to a system sound per event if a bundled file
# is somehow missing (e.g. a partial install), so feedback never goes silent.
_EARCONS = Path(__file__).resolve().parent / "earcons"
_FALLBACK = {
    "wake": _SOUNDS / "Tink.aiff",
    "endpoint": _SOUNDS / "Pop.aiff",
    "dispatch": _SOUNDS / "Glass.aiff",
    "cancel": _SOUNDS / "Funk.aiff",
    "error": _SOUNDS / "Basso.aiff",
}


def _default_for(event: str) -> Path:
    bundled = _EARCONS / f"{event}.wav"
    return bundled if bundled.exists() else _FALLBACK[event]


# Per-event default sound. wake = "I'm listening, go ahead"; endpoint = "got it,
# stopped listening"; dispatch = "agent sent"; cancel = "nothing happened";
# error = "that failed". Override any of these in the config (sound_wake /
# sound_endpoint / sound_dispatch / sound_cancel / sound_error).
DEFAULTS = {ev: _default_for(ev) for ev in _FALLBACK}

# Backwards-friendly module constants.
WAKE = DEFAULTS["wake"]
ENDPOINT = DEFAULTS["endpoint"]
DISPATCH = DEFAULTS["dispatch"]
CANCEL = DEFAULTS["cancel"]
ERROR = DEFAULTS["error"]


# A curated catalog of the built-in macOS system sounds, tagged by the role each
# fits best. "before" = plays when the wake word fires (your cue to speak);
# "endpoint" = plays when you stop talking and capture ends; "after" = plays
# when an agent is dispatched. Pick any of these by name with
# `hey-claude sounds set <event> <name>`.
CATALOG = {
    "Tink":      ("before", "light tick — default wake cue"),
    "Purr":      ("before", "gentle rising chirp"),
    "Frog":      ("before", "short croak"),
    "Pop":       ("endpoint", "soft pop — default 'stopped listening' cue"),
    "Morse":     ("endpoint", "two quick blips"),
    "Bottle":    ("endpoint", "hollow pop"),
    "Glass":     ("after",  "bright chime — default dispatch cue"),
    "Hero":      ("after",  "triumphant swell"),
    "Submarine": ("after",  "deep sonar ping"),
    "Blow":      ("after",  "breathy whoosh"),
    "Ping":      ("after",  "single clear ping"),
    "Funk":      ("cancel", "downward 'nope' — default cancel cue"),
    "Sosumi":    ("cancel", "flat beep"),
    "Basso":     ("error",  "low thud — default error cue"),
}


def catalog_paths() -> dict[str, Path]:
    """Catalog entries that actually exist on this machine."""
    return {name: _SOUNDS / f"{name}.aiff" for name in CATALOG
            if (_SOUNDS / f"{name}.aiff").exists()}


# --- soundpacks ------------------------------------------------------------
# A *soundpack* is a folder of event cues. Selecting one (config `soundpack`)
# reskins all five events at once, and any event with multiple variant files
# rotates so a repeated cue (the wake chime especially) never feels robotic.
#
# Layout — one file per event, optionally several numbered variants:
#     <pack>/wake.wav      <pack>/wake-2.wav   (rotates: wake, wake-2, wake, …)
#     <pack>/endpoint.wav  <pack>/dispatch.wav
#     <pack>/cancel.wav    <pack>/error.wav
# Any file whose stem is the event name, or starts with "<event>-"/"<event>_",
# counts as a variant; an "<event>/" subfolder of audio works too. A missing
# event falls back to the built-in default, so a partial pack still makes noise.

EVENTS = ("wake", "endpoint", "dispatch", "cancel", "error")

# Packs live as folders under soundpacks/. The default is "clicks". "studio" is
# the bundled synthesized earcons (the _EARCONS dir) — kept as the silent
# fallback for any event a pack is missing, even though it's no longer a
# user-facing pack in the catalog below.
_PACKS_DIR = Path(__file__).resolve().parent / "soundpacks"
STUDIO = "studio"
# Catalog order = display order. The five character voices first (sawyer is the
# default), then the abstract SFX packs. The voices are five distinct characters
# — each speaks a different line every time (a shuffle-bag rotation, see
# pack_event_sound), so you hear the whole personality, not one stock phrase. The
# SFX packs are CC0 (Kenney); the voices are neural-TTS (Hume Octave) — see
# soundpacks/SOURCES.md.
BUILTIN_PACKS: dict[str, str] = {
    "sawyer":    "Voice — warm Southern campfire narrator (\"I'm all ears, go ahead.\") — default.",
    "alastair": "Voice — precise British robo-butler (\"I'm listening. Go ahead.\" · \"Dispatching now.\").",
    "mara":     "Voice — mysterious, gentle wayfarer (\"Go ahead, I'm with you.\" · \"Off it goes.\").",
    "cass":     "Voice — brisk field scout (\"Listening. Go.\" · \"Command dispatched.\").",
    "sol":      "Voice — dry, deadpan night-desk (\"Go ahead, I'm listening.\" · \"Done. It's out.\").",
    "clicks":   "SFX — clean UI clicks, crisp & minimal.",
    "metal":    "SFX — metal & bells: clanks, plates, struck tin.",
    "thud":     "SFX — soft thuds, muted & low.",
}

# Per-(pack, event) shuffle-bag: maps to [variant_files, queue] so rotation
# persists across the long-running listen loop. The queue is a shuffled copy of
# the variants; we pop one per cue and reshuffle a fresh bag when it empties, so
# you hear *every* line once before any repeats, in a fresh random order each
# pass (never the same line twice in a row). Re-seeded if the variant set changes
# (e.g. the user drops a file in mid-run).
_rotation: dict[tuple[str, str], list] = {}


def _shuffled_bag(files: list[Path], avoid: Optional[Path]) -> list[Path]:
    """A freshly shuffled copy of ``files``; if ``avoid`` would land first (the
    line we just played), rotate it deeper so we never repeat back-to-back."""
    bag = list(files)
    random.shuffle(bag)
    if avoid is not None and len(bag) > 1 and bag[-1] == avoid:
        # bag is consumed from the end (pop()), so bag[-1] plays next.
        bag[-1], bag[0] = bag[0], bag[-1]
    return bag


def user_packs_dir() -> Path:
    """Where a user drops their own packs: ``<config>/soundpacks/<name>/``."""
    from .config import config_home  # local import keeps this module import-light
    return config_home() / "soundpacks"


def pack_dir(name: str) -> Optional[Path]:
    """Resolve a pack name to its folder. A user pack shadows a builtin of the
    same name; ``studio`` maps to the bundled earcons."""
    name = (name or "").strip()
    if not name:
        return None
    user = user_packs_dir() / name
    if user.is_dir():
        return user
    if name == STUDIO:
        return _EARCONS if _EARCONS.is_dir() else None
    builtin = _PACKS_DIR / name
    return builtin if builtin.is_dir() else None


def list_packs() -> dict[str, tuple[str, str]]:
    """All available packs → (source, description). Builtins first (in their
    canonical order), then any custom packs found in the user dir."""
    packs: dict[str, tuple[str, str]] = {}
    for name, desc in BUILTIN_PACKS.items():
        src = "custom" if (user_packs_dir() / name).is_dir() else "built-in"
        packs[name] = (src, desc)
    user_root = user_packs_dir()
    if user_root.is_dir():
        for child in sorted(user_root.iterdir()):
            if child.is_dir() and child.name not in packs:
                packs[child.name] = ("custom", f"your pack — {child}")
    return packs


def pack_event_files(pack: str, event: str) -> list[Path]:
    """Sorted variant files for ``event`` within ``pack`` (empty if none)."""
    d = pack_dir(pack)
    if d is None:
        return []
    found: list[Path] = []
    subdir = d / event
    if subdir.is_dir():
        found = [p for p in subdir.iterdir()
                 if p.is_file() and p.suffix.lower() in _AUDIO_EXTS]
    else:
        for p in d.iterdir():
            if not p.is_file() or p.suffix.lower() not in _AUDIO_EXTS:
                continue
            stem = p.stem
            if stem == event or stem.startswith(f"{event}-") or stem.startswith(f"{event}_"):
                found.append(p)
    # Bare "<event>" first, then numbered variants in name order, so rotation
    # leads with the primary cue (wake.wav, then wake-2.wav, …).
    return sorted(found, key=lambda p: (0 if p.stem == event else 1, p.name))


def pack_event_sound(pack: str, event: str) -> Optional[Path]:
    """Next sound for ``event`` in ``pack`` via a shuffle-bag over its variants.

    Each variant plays once per pass in a random order; when the bag empties we
    reshuffle (never repeating the just-played line first), so a character speaks
    its whole range of lines, varied, rather than looping one stock phrase.

    Returns ``None`` when the pack has nothing for this event (the caller falls
    back to the built-in default), so a partial custom pack never goes silent.
    """
    files = pack_event_files(pack, event)
    if not files:
        return None
    if len(files) == 1:
        return files[0]
    key = (pack, event)
    state = _rotation.get(key)
    if state is None or state[0] != files:  # first use, or the variant set changed
        state = [files, _shuffled_bag(files, avoid=None)]
        _rotation[key] = state
    bag = state[1]
    if not bag:  # bag exhausted — reshuffle a fresh pass
        last = state[2] if len(state) > 2 else None
        bag = _shuffled_bag(files, avoid=last)
        state[1] = bag
    chosen = bag.pop()
    if len(state) > 2:
        state[2] = chosen
    else:
        state.append(chosen)
    return chosen


def resolve(event: str, override: str = "") -> Optional[Path]:
    """Pick the sound file for an event, honoring a config override.

    A bare event name resolves a macOS system sound (so ``sound_wake = "Hero"``
    works, no path needed). An override of "none"/"off" silences just that event.
    Returns ``None`` when the event should be silent.
    """
    override = (override or "").strip()
    if override.lower() in ("none", "off", "silent"):
        return None
    if override:
        p = Path(override).expanduser()
        if p.exists():
            return p
        earcon = _EARCONS / f"{override}.wav"  # a bundled hey-claude earcon name
        if earcon.exists():
            return earcon
        named = _SOUNDS / f"{override}.aiff"  # treat as a system-sound name
        if named.exists():
            return named
        return None  # configured but missing — stay quiet rather than guess
    return DEFAULTS.get(event)


def event_sound(event: str, override: str = "", pack: str = "") -> Optional[Path]:
    """The sound to actually play for ``event``, honoring precedence:

    1. a per-event ``sound_<event>`` override (a path/name, or "none" to silence);
    2. the active ``pack`` (rotating through its variants for this event);
    3. the built-in default earcon.

    A per-event override is the most specific intent, so it wins even over a
    selected pack. With no override and no pack hit, we fall through to the
    studio default — feedback never goes silent by accident.
    """
    override = (override or "").strip()
    if override:
        # "none"/path/name all handled here; an explicit override always wins.
        return resolve(event, override)
    pack = (pack or "").strip()
    if pack and pack != STUDIO:
        chosen = pack_event_sound(pack, event)
        if chosen is not None:
            return chosen
    return DEFAULTS.get(event)


def play(sound: Optional[Path], enabled: bool = True) -> None:
    if not enabled or sound is None or not sound.exists():
        return
    try:
        subprocess.Popen(
            ["afplay", str(sound)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, ValueError):
        # afplay missing or sandboxed audio — feedback is best-effort, never fatal.
        pass


def wake(enabled: bool = True) -> None:
    play(DEFAULTS["wake"], enabled)


def endpoint(enabled: bool = True) -> None:
    play(DEFAULTS["endpoint"], enabled)


def dispatch(enabled: bool = True) -> None:
    play(DEFAULTS["dispatch"], enabled)


def cancel(enabled: bool = True) -> None:
    play(DEFAULTS["cancel"], enabled)


def error(enabled: bool = True) -> None:
    play(DEFAULTS["error"], enabled)
