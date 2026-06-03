"""Microphone capture and command endpointing.

A single persistent input stream feeds a queue (so no frames are dropped while
we're busy), exposing uniform 80 ms / 1280-sample int16 frames at 16 kHz — the
exact shape openWakeWord wants. ``record_command`` then consumes from that same
stream and uses a simple, well-behaved energy VAD to capture everything the user
says after the wake word, stopping on trailing silence.
"""

from __future__ import annotations

import queue
from collections import deque
from typing import Optional

import numpy as np

# openWakeWord expects 1280-sample (80 ms @ 16 kHz) int16 frames.
FRAME_SAMPLES = 1280


class MicError(RuntimeError):
    """Raised when the microphone can't be opened or audio deps are missing."""


def _import_sd():
    try:
        import sounddevice as sd  # noqa: PLC0415
    except OSError as exc:  # PortAudio not installed
        raise MicError(
            "PortAudio is not available. Install it with:  brew install portaudio\n"
            f"(underlying error: {exc})"
        ) from exc
    except ModuleNotFoundError as exc:
        raise MicError(
            "The 'sounddevice' package is not installed. Install it with:  "
            "pip install sounddevice"
        ) from exc
    return sd


def resolve_device(name: str):
    """Map a config ``mic_device`` (index or name substring) to a sounddevice id."""
    if not name:
        return None
    name = name.strip()
    if name.isdigit():
        return int(name)
    sd = _import_sd()
    for idx, dev in enumerate(sd.query_devices()):
        if dev.get("max_input_channels", 0) > 0 and name.lower() in dev["name"].lower():
            return idx
    raise MicError(f"No input device matching {name!r}. Run `hey-claude doctor` to list devices.")


def list_input_devices() -> list[tuple[int, str, int]]:
    """Return (index, name, default_samplerate) for every input-capable device."""
    sd = _import_sd()
    out = []
    for idx, dev in enumerate(sd.query_devices()):
        if dev.get("max_input_channels", 0) > 0:
            out.append((idx, dev["name"], int(dev.get("default_samplerate", 0))))
    return out


class Microphone:
    """A callback-fed 16 kHz mono int16 mic stream yielding fixed-size frames."""

    def __init__(self, samplerate: int = 16000, device: Optional[object] = None):
        self.samplerate = samplerate
        self.device = device
        self._sd = _import_sd()
        self._q: "queue.Queue[np.ndarray]" = queue.Queue()
        self._stream = None

    def _callback(self, indata, frames, time_info, status):  # noqa: ARG002
        # indata is int16 shape (frames, 1); copy because the buffer is reused.
        self._q.put(indata[:, 0].copy())

    def __enter__(self) -> "Microphone":
        try:
            self._stream = self._sd.InputStream(
                samplerate=self.samplerate,
                channels=1,
                dtype="int16",
                blocksize=FRAME_SAMPLES,
                device=self.device,
                callback=self._callback,
            )
            self._stream.start()
        except Exception as exc:  # PortAudioError, etc.
            raise MicError(
                f"Could not open the microphone: {exc}\n"
                "If this is the first run, grant microphone access in\n"
                "System Settings → Privacy & Security → Microphone, then try again.\n"
                "A launchd/CLI process often can't show that prompt — see "
                "`hey-claude app` to install a permission-stable .app."
            ) from exc
        return self

    def __exit__(self, *exc) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def read(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """Return the next int16 frame, or None if none arrived within ``timeout``."""
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain(self) -> None:
        """Discard any buffered frames (e.g. the tail of the wake word itself)."""
        try:
            while True:
                self._q.get_nowait()
        except queue.Empty:
            return


def _rms(frame: np.ndarray) -> float:
    if frame.size == 0:
        return 0.0
    x = frame.astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(x * x)))


def record_command(
    mic: Microphone,
    *,
    silence_ms: int = 1000,
    grace_ms: int = 2000,
    max_seconds: float = 15.0,
    preroll_ms: int = 300,
    start_rms: float = 0.012,
    keep_rms: float = 0.008,
    min_speech_ms: int = 350,
    onset_timeout_s: float = 4.0,
) -> Optional[np.ndarray]:
    """Capture the spoken command after the wake word.

    Endpointing uses a **two-phase** trailing-silence window so an indecisive
    speaker who pauses to think isn't cut off mid-command:

    * while they've barely spoken (less than ``min_speech_ms`` of voiced audio so
      far — i.e. still gathering their thought), a pause is tolerated up to the
      longer ``grace_ms`` before giving up, and
    * once a real command has been spoken, a normal ``silence_ms`` of trailing
      quiet ends the capture so dispatch stays snappy.

    Returns a float32 array in [-1, 1] at the mic's sample rate, or ``None`` if
    nothing worth transcribing was captured. ``None`` happens in two cases:

    * **no onset** — no frame crossed ``start_rms`` within ``onset_timeout_s``
      (a bare "hey claude" with no command), or
    * **failed the energy gate** — speech started but fewer than
      ``min_speech_ms`` of audio actually stayed above ``keep_rms``. This is the
      decibel "first line of defense": it drops captures that are really just
      the wake-word tail, a cough, or room noise, so Whisper is never handed
      near-silence to hallucinate words from.
    """
    frame_ms = FRAME_SAMPLES / mic.samplerate * 1000.0
    silence_frames = max(1, int(silence_ms / frame_ms))
    grace_frames = max(silence_frames, int(grace_ms / frame_ms))
    preroll_frames = max(0, int(preroll_ms / frame_ms))
    onset_frames = max(1, int(onset_timeout_s * 1000 / frame_ms))
    max_frames = max(1, int(max_seconds * 1000 / frame_ms))
    min_voiced_frames = max(1, int(min_speech_ms / frame_ms))

    preroll: deque[np.ndarray] = deque(maxlen=preroll_frames)
    captured: list[np.ndarray] = []
    started = False
    silent_run = 0
    voiced_frames = 0  # frames above keep_rms — the real "how much did they say"
    waited = 0
    stalls = 0  # consecutive empty reads while capturing (mic stalled / stopped)

    while len(captured) < max_frames:
        frame = mic.read(timeout=1.0)
        if frame is None:
            if not started:
                waited += int(1000 / frame_ms)
                if waited >= onset_frames:
                    return None
            else:
                # No audio arrived for ~1s mid-capture: the stream stalled or was
                # stopped. End the utterance rather than wait on a dead mic — the
                # grace window only protects against *quiet*, not silence-of-no-frames.
                stalls += 1
                if stalls >= 2:
                    break
            continue
        stalls = 0

        level = _rms(frame)
        if not started:
            preroll.append(frame)
            waited += 1
            if level >= start_rms:
                started = True
                captured.extend(preroll)
                captured.append(frame)
                voiced_frames = 1
                silent_run = 0
            elif waited >= onset_frames:
                return None  # they said the wake word but never spoke a command
        else:
            captured.append(frame)
            if level >= keep_rms:
                voiced_frames += 1
                silent_run = 0
            else:
                silent_run += 1
                # Long grace while they're still mid-thought (little said yet),
                # tightening to the normal trailing window once a real command
                # has landed.
                limit = silence_frames if voiced_frames >= min_voiced_frames else grace_frames
                if silent_run >= limit:
                    break

    if not captured:
        return None
    # Energy gate: require a real minimum of voiced audio. Without this, a single
    # loud onset frame (the wake-word tail) followed by a pause sails through and
    # Whisper invents text from the silence.
    if voiced_frames < min_voiced_frames:
        return None
    audio = np.concatenate(captured).astype(np.float32) / 32768.0
    return audio
