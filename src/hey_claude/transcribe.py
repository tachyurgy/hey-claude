"""Speech-to-text for the spoken command, via Apple MLX Whisper.

MLX runs on the Apple-Silicon GPU (Metal) and transcribes a short command in
well under a second with the turbo model. We pass the audio as an in-memory
float32 array, so there's no temp file and no ffmpeg dependency.
"""

from __future__ import annotations

import os

import numpy as np

# Silence huggingface_hub's download chatter ("Fetching N files", "Download
# complete") that fires the first time a model is pulled. Set before the hub is
# ever imported. This is cosmetic only — a voice tool should be quiet, not spew
# tqdm bars at the user every time it thinks.
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")


class TranscribeError(RuntimeError):
    pass


def _import_mlx():
    try:
        import mlx_whisper  # noqa: PLC0415
    except ModuleNotFoundError as exc:
        raise TranscribeError(
            "mlx-whisper is not installed (Apple Silicon only). Install it with:  "
            "pip install mlx-whisper"
        ) from exc
    return mlx_whisper


def transcribe(audio: np.ndarray, model: str) -> str:
    """Transcribe a float32 [-1,1] 16 kHz mono array to stripped text."""
    mlx_whisper = _import_mlx()
    audio = np.asarray(audio, dtype=np.float32)
    result = mlx_whisper.transcribe(
        audio,
        path_or_hf_repo=model,
        # A command is one short English utterance; greedy + no timestamps is fastest.
        language="en",
        fp16=True,
        # verbose=None hides BOTH the decoded-text dump and tqdm's per-frame
        # progress bar (mlx-whisper only shows the bar when verbose is *False*).
        verbose=None,
        # Single greedy pass: deterministic, fast, and — crucially — it skips the
        # temperature-fallback ladder that makes Whisper "try harder" on silence
        # and invent words. Paired with the energy gate in audio.py, this is what
        # stops a quiet pause from being transcribed as random text.
        temperature=0.0,
        condition_on_previous_text=False,
    )
    return (result.get("text") or "").strip()


def warm(model: str) -> None:
    """Preload model weights so the first real transcription isn't slow.

    Best-effort: a failure here just means a slightly slower first command.
    """
    try:
        silence = np.zeros(16000, dtype=np.float32)
        transcribe(silence, model)
    except Exception:
        pass
