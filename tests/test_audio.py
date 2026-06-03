"""Command capture endpointing — especially the energy ('decibel') gate that
keeps near-silence from reaching Whisper and being hallucinated into words."""

import numpy as np

from hey_claude.audio import FRAME_SAMPLES, record_command


class FakeMic:
    """A microphone stand-in that replays a fixed list of int16 frames."""

    samplerate = 16000

    def __init__(self, frames):
        self._frames = list(frames)

    def read(self, timeout=1.0):  # noqa: ARG002
        return self._frames.pop(0) if self._frames else None


def _frame(rms_norm):
    """A 1280-sample int16 frame whose RMS is ``rms_norm`` in [0,1] units."""
    value = int(rms_norm * 32768)
    return np.full(FRAME_SAMPLES, value, dtype=np.int16)


VOICED = _frame(0.05)   # well above start/keep thresholds
SILENT = _frame(0.0)
TAIL = [SILENT] * 12     # enough trailing silence to end the capture (silence_ms=800)


def test_gate_rejects_a_single_loud_blip_then_silence():
    # One loud onset frame (e.g. the wake-word tail) then a pause: must be dropped,
    # not handed to the transcriber.
    mic = FakeMic([VOICED] + TAIL)
    assert record_command(mic, min_speech_ms=350) is None


def test_gate_passes_real_speech():
    # A sustained utterance clears the gate and returns audio.
    mic = FakeMic([VOICED] * 8 + TAIL)
    audio = record_command(mic, min_speech_ms=350)
    assert audio is not None
    assert audio.dtype == np.float32
    assert audio.size > 0


def test_no_onset_returns_none():
    # Pure silence: never crosses the onset threshold, so nothing is captured.
    mic = FakeMic([SILENT] * 20)
    assert record_command(mic, onset_timeout_s=0.5) is None
