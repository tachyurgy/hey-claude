"""Wake-word detection engines and phrase matching.

Two engines share a phrase matcher:

* ``OpenWakeWordEngine`` — the default. A tiny always-on classifier scores each
  80 ms frame; a score over the threshold (outside the refractory window) is a
  wake. Lowest CPU/battery, but needs a trained ``hey_claude.onnx`` (see
  ``hey-claude train``).
* ``WhisperWakeEngine`` — no model file. The listener transcribes each utterance
  and this matcher decides whether it began with the wake phrase, returning the
  remainder as the command in one pass. Works out of the box; more CPU.
"""

from __future__ import annotations

import re
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # numpy is only referenced in type hints here
    import numpy as np

_WORD = re.compile(r"[a-z']+")
# Tolerated mishearings of the two phrase tokens, so "hey, Claude" / "hi Claude"
# / "hey clyde" still fire without retraining anything.
_HEY = {"hey", "hay", "hi", "hello", "ey", "a"}
_CLAUDE = {"claude", "clod", "cloud", "clyde", "claud", "klaud", "clawed", "claus"}


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _close(token: str, candidates: set[str], ratio: float = 0.8) -> bool:
    if token in candidates:
        return True
    return any(SequenceMatcher(None, token, c).ratio() >= ratio for c in candidates)


def match_wake(text: str, phrase: str = "hey claude") -> Optional[str]:
    """If ``text`` begins with the wake phrase, return the command remainder.

    Returns "" when the user said only the wake phrase, or ``None`` when the
    phrase isn't present at the start. Tolerant of punctuation and common
    mishearings ("hey, Claude, ...", "hi Claude ...").
    """
    toks = _tokens(text)
    if not toks:
        return None

    phrase_toks = _tokens(phrase) or ["hey", "claude"]
    # Fast path: exact-ish two-token "hey claude".
    if len(phrase_toks) == 2 and _close(toks[0], _HEY) and len(toks) >= 2 and _close(toks[1], _CLAUDE):
        return " ".join(toks[2:]).strip()

    # General path: does the phrase appear (fuzzily) as a prefix?
    if len(toks) >= len(phrase_toks):
        if all(SequenceMatcher(None, a, b).ratio() >= 0.78 for a, b in zip(toks, phrase_toks)):
            return " ".join(toks[len(phrase_toks):]).strip()

    # Single-token "claude" alone also counts as a wake (command may follow).
    if _close(toks[0], _CLAUDE):
        return " ".join(toks[1:]).strip()
    return None


class WakeError(RuntimeError):
    pass


def ensure_base_models() -> None:
    """Download openWakeWord's shared melspectrogram + embedding backbone (once)."""
    try:
        import openwakeword  # noqa: PLC0415
    except ModuleNotFoundError as exc:
        raise WakeError(
            "openwakeword is not installed. Install it with:  pip install openwakeword"
        ) from exc
    try:
        openwakeword.utils.download_models()
    except Exception as exc:  # network or layout issue
        raise WakeError(f"Could not download openWakeWord base models: {exc}") from exc


class OpenWakeWordEngine:
    """Frame-level wake detector backed by a trained ``.onnx`` classifier head."""

    def __init__(self, model_path: Path, threshold: float = 0.5, refractory_s: float = 2.0):
        self.model_path = Path(model_path)
        self.threshold = threshold
        self.refractory_s = refractory_s
        self._last_fire = 0.0
        self._model = None
        if not self.model_path.exists():
            raise WakeError(
                f"Wake-word model not found: {self.model_path}\n"
                "Train one (no mic, ~10 min, free) with:  hey-claude train\n"
                "or switch to the no-model engine:        hey-claude config set engine whisper"
            )

    def load(self) -> None:
        ensure_base_models()
        from openwakeword.model import Model  # noqa: PLC0415

        try:
            self._model = Model(
                wakeword_models=[str(self.model_path)],
                inference_framework="onnx",
            )
        except Exception as exc:
            raise WakeError(
                f"Failed to load wake model {self.model_path}: {exc}\n"
                "Ensure onnxruntime is installed:  pip install onnxruntime"
            ) from exc

    def process(self, frame: np.ndarray) -> bool:
        """Feed one int16 frame; return True on a (debounced) wake detection."""
        if self._model is None:
            self.load()
        scores = self._model.predict(frame)  # type: ignore[union-attr]
        score = max(scores.values()) if scores else 0.0
        if score < self.threshold:
            return False
        now = time.monotonic()
        if now - self._last_fire < self.refractory_s:
            return False
        self._last_fire = now
        return True


class WhisperWakeEngine:
    """Utterance-level wake matcher for the no-model fallback engine."""

    def __init__(self, phrase: str = "hey claude"):
        self.phrase = phrase

    def extract(self, transcript: str) -> Optional[str]:
        """Return the command if ``transcript`` started with the wake phrase."""
        return match_wake(transcript, self.phrase)
