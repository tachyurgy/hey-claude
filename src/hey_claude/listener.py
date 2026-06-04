"""The listen loop: wake → capture command → transcribe → dispatch.

Holds one open microphone and dispatches to the configured launch mode. Both
wake engines funnel into the same ``_dispatch`` tail so command capture,
transcription cleanup, confirmation, and feedback are defined once.
"""

from __future__ import annotations

import sys

from . import sounds
from .audio import Microphone, MicError, record_command, resolve_device
from .config import Config
from .launcher import LaunchError, launch
from .transcribe import TranscribeError, transcribe, warm
from .wake import OpenWakeWordEngine, WakeError, WhisperWakeEngine, match_wake


class Listener:
    def __init__(self, config: Config):
        self.cfg = config
        self.running = False

    # -- output helpers ----------------------------------------------------
    def _say(self, msg: str) -> None:
        if self.cfg.verbose:
            print(msg, flush=True)

    def _chime(self, event: str) -> None:
        override = {
            "wake": self.cfg.sound_wake,
            "endpoint": self.cfg.sound_endpoint,
            "dispatch": self.cfg.sound_dispatch,
            "cancel": self.cfg.sound_cancel,
            "error": self.cfg.sound_error,
        }.get(event, "")
        sounds.play(
            sounds.event_sound(event, override, self.cfg.soundpack),
            self.cfg.chime,
        )

    def _clean(self, text: str) -> str:
        text = text.strip()
        # If the wake phrase leaked into the captured command, strip it.
        stripped = match_wake(text, self.cfg.wake_phrase)
        if stripped is not None and stripped:
            return stripped
        return text

    # -- shared dispatch tail ---------------------------------------------
    def _dispatch_command(self, command: str) -> None:
        command = self._clean(command)
        if len(command) < 2:
            self._say("  … no command heard.")
            self._chime("cancel")
            return

        if self.cfg.confirm:
            sys.stdout.write(f'  dispatch "{command}"?  [Enter to send, anything else to cancel] ')
            sys.stdout.flush()
            if sys.stdin.readline().strip():
                self._say("  cancelled.")
                self._chime("cancel")
                return

        try:
            result = launch(self.cfg, command)
        except LaunchError as exc:
            self._say(f"  ⚠ {exc}")
            self._chime("error")
            return

        self._chime("dispatch")
        if result.mode == "bg":
            self._say(f'  ✅ dispatched · {result.detail}  →  claude attach {result.detail}')
        elif result.mode == "print":
            self._say(f"  ✅ headless agent running · logging to {result.detail}")
        else:
            self._say(f"  ✅ {result.detail}")

    def _capture_then_dispatch(self, mic: Microphone) -> None:
        """openWakeWord path: record the command after the wake word."""
        # Discard the tail of the wake word (and the wake chime) still sitting in
        # the queue, so command capture doesn't trigger its onset on "…laude" and
        # then end on your natural pause before you've actually said anything.
        mic.drain()
        self._chime("wake")
        self._say("🎙  listening for your command…")
        audio = record_command(
            mic,
            silence_ms=self.cfg.silence_ms,
            grace_ms=self.cfg.endpoint_grace_ms,
            max_seconds=self.cfg.max_command_seconds,
            preroll_ms=self.cfg.preroll_ms,
            start_rms=self.cfg.vad_start_rms,
            keep_rms=self.cfg.vad_keep_rms,
            min_speech_ms=self.cfg.min_command_ms,
        )
        if audio is None:
            self._say("  … no command heard.")
            self._chime("cancel")
            return
        # Capture ended (you stopped talking) — cue that before the silent
        # transcription gap, so you know it heard you and is now thinking.
        self._chime("endpoint")
        self._say("  · got it — transcribing…")
        try:
            text = transcribe(audio, self.cfg.whisper_model)
        except TranscribeError as exc:
            self._say(f"  ⚠ {exc}")
            self._chime("error")
            return
        self._say(f'  heard: "{text}"')
        self._dispatch_command(text)

    # -- engines -----------------------------------------------------------
    def _run_openwakeword(self) -> None:
        engine = OpenWakeWordEngine(
            self.cfg.resolved_model_path(),
            threshold=self.cfg.threshold,
            refractory_s=self.cfg.refractory_seconds,
        )
        self._say("· loading wake-word model…")
        engine.load()
        self._say("· warming Whisper…")
        warm(self.cfg.whisper_model)
        device = resolve_device(self.cfg.mic_device)
        self._banner()
        with Microphone(self.cfg.samplerate, device) as mic:
            self.running = True
            while self.running:
                frame = mic.read(timeout=1.0)
                if frame is None:
                    continue
                if engine.process(frame):
                    self._say(f'\n👂 "{self.cfg.wake_phrase}" detected')
                    self._capture_then_dispatch(mic)
                    # Clear the wake-word activation still sitting in the model's
                    # buffer and re-arm the refractory window, then drop any audio
                    # captured while we were busy — otherwise the lingering "hey
                    # claude" (or chime/agent feedback) re-fires immediately.
                    engine.reset()
                    mic.drain()

    def _run_whisper(self) -> None:
        matcher = WhisperWakeEngine(self.cfg.wake_phrase)
        self._say("· warming Whisper (wake + command)…")
        warm(self.cfg.whisper_wake_model)
        warm(self.cfg.whisper_model)
        device = resolve_device(self.cfg.mic_device)
        self._banner()
        with Microphone(self.cfg.samplerate, device) as mic:
            self.running = True
            while self.running:
                utt = record_command(
                    mic,
                    silence_ms=self.cfg.silence_ms,
                    grace_ms=self.cfg.endpoint_grace_ms,
                    max_seconds=self.cfg.max_command_seconds,
                    preroll_ms=self.cfg.preroll_ms,
                    start_rms=self.cfg.vad_start_rms,
                    keep_rms=self.cfg.vad_keep_rms,
                    min_speech_ms=self.cfg.min_command_ms,
                    onset_timeout_s=1.0,  # short, so the loop keeps polling
                )
                if utt is None:
                    continue
                try:
                    rough = transcribe(utt, self.cfg.whisper_wake_model)
                except TranscribeError as exc:
                    self._say(f"  ⚠ {exc}")
                    continue
                command = matcher.extract(rough)
                if command is None:
                    continue  # utterance didn't start with the wake phrase
                self._say(f'\n👂 "{self.cfg.wake_phrase}" detected')
                if command:
                    # Re-transcribe the whole utterance accurately, then re-strip.
                    try:
                        fine = transcribe(utt, self.cfg.whisper_model)
                        command = matcher.extract(fine) or command
                    except TranscribeError:
                        pass
                    self._say(f'  heard: "{command}"')
                    self._chime("wake")
                    self._dispatch_command(command)
                else:
                    # Wake phrase only — capture the command in a second breath.
                    self._capture_then_dispatch(mic)
                mic.drain()

    # -- entry -------------------------------------------------------------
    def _banner(self) -> None:
        if self.cfg.launch_template.strip():
            mode = f"custom template ({self.cfg.launch_template})"
        else:
            mode = {"bg": "background agent (claude --bg)",
                    "terminal": "new Terminal session",
                    "print": "headless (claude -p)"}.get(self.cfg.launch_mode, self.cfg.launch_mode)
        self._say("")
        self._say(f'  hey-claude is listening — say "{self.cfg.wake_phrase}, <your task>"')
        self._say(f"  engine: {self.cfg.engine}   launch: {mode}")
        self._say("  press Ctrl-C to stop")
        self._say("")

    def run(self) -> int:
        try:
            if self.cfg.engine == "whisper":
                self._run_whisper()
            else:
                self._run_openwakeword()
        except KeyboardInterrupt:
            self._say("\n· stopped.")
            return 0
        except (MicError, WakeError) as exc:
            print(f"\nerror: {exc}", file=sys.stderr)
            return 1
        return 0

    def stop(self) -> None:
        self.running = False
