"""Non-blocking audible feedback via macOS ``afplay`` and system sounds.

Audible cues matter for a voice tool: you need to know the wake word registered
*before* you start speaking the command, and that a dispatch actually happened.
All playback is fire-and-forget so it never stalls the listen loop.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

_SOUNDS = Path("/System/Library/Sounds")

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
