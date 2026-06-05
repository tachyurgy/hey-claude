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
    """Download only the shared backbone the ONNX engine actually loads (once).

    openWakeWord's own ``download_models()`` helper, called with no arguments,
    pulls the *entire* pretrained classifier zoo (alexa, hey_mycroft, hey_jarvis,
    hey_rhasspy, timer — each as both .tflite and .onnx) on top of the backbone.
    We never use any of those — we load our own ``hey_claude.onnx`` — so fetching
    them just spams a long download list on first run. The ONNX engine needs
    exactly three files: ``melspectrogram.onnx``, ``embedding_model.onnx`` and
    ``silero_vad.onnx``. Grab those and nothing else.
    """
    try:
        import openwakeword  # noqa: PLC0415
        from openwakeword.utils import download_file  # noqa: PLC0415
    except ModuleNotFoundError as exc:
        raise WakeError(
            "openwakeword is not installed. Install it with:  pip install openwakeword"
        ) from exc

    import os  # noqa: PLC0415

    target_dir = os.path.join(os.path.dirname(openwakeword.__file__), "resources", "models")
    os.makedirs(target_dir, exist_ok=True)

    # Feature backbone: their dicts list the .tflite url; the ONNX engine loads
    # the .onnx sibling, so swap the extension and fetch only that.
    urls = [m["download_url"].replace(".tflite", ".onnx") for m in openwakeword.FEATURE_MODELS.values()]
    urls += [m["download_url"] for m in openwakeword.VAD_MODELS.values()]  # already .onnx

    try:
        for url in urls:
            dest = os.path.join(target_dir, url.split("/")[-1])
            if not os.path.exists(dest):
                download_file(url, target_dir)
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
                "Pick a bundled wake word:                 hey-claude models use hey_claude\n"
                "or train your own (no mic, ~10 min, free): hey-claude train\n"
                "or switch to the no-model engine:          hey-claude config set engine whisper"
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

    def reset(self) -> None:
        """Clear the model's rolling prediction buffer and re-arm the refractory
        window. Call this *after* handling a command.

        The wake phrase spans ~1 s (~12 frames), so its activation lingers in
        openWakeWord's internal buffer across many frames. Capturing,
        transcribing, and dispatching the command takes several seconds — long
        enough that the 2 s refractory measured from the *detection* has already
        expired by the time we resume. Without clearing the buffer and restarting
        the clock here, the very next frames re-score the same lingering "hey
        claude" and fire again, storming the loop with phantom detections."""
        if self._model is not None:
            try:
                self._model.reset()
            except Exception:  # best-effort; never crash the listen loop
                pass
        self._last_fire = time.monotonic()


class WhisperWakeEngine:
    """Utterance-level wake matcher for the no-model fallback engine."""

    def __init__(self, phrase: str = "hey claude"):
        self.phrase = phrase

    def extract(self, transcript: str) -> Optional[str]:
        """Return the command if ``transcript`` started with the wake phrase."""
        return match_wake(transcript, self.phrase)
