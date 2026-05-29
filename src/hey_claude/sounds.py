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

# Built-in defaults. Tink = "I heard you, go ahead"; Glass = "agent dispatched";
# Funk = "nothing happened"; Basso = "error". Override any of these per-event in
# the config (sound_wake / sound_dispatch / sound_cancel / sound_error).
DEFAULTS = {
    "wake": _SOUNDS / "Tink.aiff",
    "dispatch": _SOUNDS / "Glass.aiff",
    "cancel": _SOUNDS / "Funk.aiff",
    "error": _SOUNDS / "Basso.aiff",
}

# Backwards-friendly module constants.
WAKE = DEFAULTS["wake"]
DISPATCH = DEFAULTS["dispatch"]
CANCEL = DEFAULTS["cancel"]
ERROR = DEFAULTS["error"]


# A curated catalog of the built-in macOS system sounds, tagged by the role each
# fits best. "before" = plays when the wake word fires (your cue to speak the
# command); "after" = plays when an agent is dispatched. Pick any of these by
# name with `hey-claude sounds set <event> <name>`.
CATALOG = {
    "Tink":      ("before", "light tick — default wake cue"),
    "Pop":       ("before", "soft pop"),
    "Morse":     ("before", "two quick blips"),
    "Purr":      ("before", "gentle rising chirp"),
    "Bottle":    ("before", "hollow pop"),
    "Frog":      ("before", "short croak"),
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


def dispatch(enabled: bool = True) -> None:
    play(DEFAULTS["dispatch"], enabled)


def cancel(enabled: bool = True) -> None:
    play(DEFAULTS["cancel"], enabled)


def error(enabled: bool = True) -> None:
    play(DEFAULTS["error"], enabled)
