"""Catalog of the wake-word models shipped with hey-claude.

These ``.onnx`` files live next to this module and are bundled into the wheel as
package data, so ``hey-claude`` works the moment it is installed — no training
step. They are openWakeWord classifier heads trained on 100% synthetic speech
(Piper TTS), so they are speaker-independent and respond to anyone's voice.

Quality disclaimer (read this): these are small models trained on a modest
synthetic-speech budget. **Your mileage may vary** — accuracy and the
false-positive rate depend on your microphone, room, accent, and how you say the
phrase. Tune ``threshold`` up if it fires when it shouldn't, down if it misses
you. If a bundled model is not reliable enough for you, train your own dialed-in
model with ``hey-claude train`` (still no microphone, ~10 min, free).
"""

from __future__ import annotations

from pathlib import Path

BUNDLED_DIR = Path(__file__).resolve().parent

# name (== filename stem) -> (spoken phrase, one-line note)
CATALOG: dict[str, tuple[str, str]] = {
    "hey_claude": ("hey claude", "Default. The phrase the tool is named for."),
    "okay_claude": ("okay claude", 'Alternate Claude trigger ("okay claude").'),
    "hey_computer": ("hey computer", "Star-Trek style; distinct from any product name."),
    "hey_assistant": ("hey assistant", "Generic, agent-neutral trigger."),
    "hey_agent": ("hey agent", "Generic, agent-neutral trigger."),
}

DEFAULT = "hey_claude"


def bundled_path(name: str) -> Path | None:
    """Absolute path to a bundled model by name (stem), or ``None`` if absent."""
    p = BUNDLED_DIR / f"{name}.onnx"
    return p if p.exists() else None


def available() -> list[str]:
    """Bundled model names that are actually present on disk, catalog order first."""
    present = [n for n in CATALOG if (BUNDLED_DIR / f"{n}.onnx").exists()]
    extra = sorted(
        p.stem for p in BUNDLED_DIR.glob("*.onnx") if p.stem not in CATALOG
    )
    return present + extra
