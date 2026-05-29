"""hey-claude — say "Hey Claude" and dispatch a Claude Code background agent.

A fully on-device voice wake word for macOS. The pipeline is:

    mic → openWakeWord ("hey claude") → endpoint the command by silence
        → MLX Whisper (transcribe the command) → ``claude --bg "<command>"``

Nothing leaves the machine except the prompt you ask Claude Code to act on,
which goes wherever Claude Code already sends it. No cloud wake word, no API
key for listening, no per-user signup.
"""

from .version import __version__

__all__ = ["__version__"]
