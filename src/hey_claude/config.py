"""Configuration: a small typed record persisted as TOML.

Read with the stdlib ``tomllib`` (Python 3.11+); written with a tiny hand-rolled
serializer so we don't pull in a TOML *writer* dependency. The schema is flat
and only contains strings, numbers, and booleans, which keeps the writer honest.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - 3.10 fallback
    tomllib = None  # type: ignore[assignment]


APP_NAME = "hey-claude"


def config_home() -> Path:
    """Base directory for config + models. Honors ``HEY_CLAUDE_HOME``/``XDG_CONFIG_HOME``."""
    override = os.environ.get("HEY_CLAUDE_HOME")
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / APP_NAME


def config_path() -> Path:
    return config_home() / "config.toml"


def models_dir() -> Path:
    return config_home() / "models"


def log_path() -> Path:
    return config_home() / "hey-claude.log"


def resolve_wakeword(value: str) -> Path:
    """Resolve a ``wakeword_model`` config value to a concrete model file.

    Accepts, in order: an explicit filesystem path; a *bundled* model name like
    ``hey_claude`` (or ``okay_claude``, ``hey_computer`` …, shipped in the wheel);
    a model installed under ``models_dir()``. Falls back to the bundled default so
    a fresh install works with no training step.
    """
    from .models import bundled_path  # local import: keeps config import-light

    if value:
        p = Path(value).expanduser()
        if p.suffix and (p.exists() or p.is_absolute() or "/" in value):
            return p
        # A bare name: try a bundled model, then an installed one.
        bp = bundled_path(value)
        if bp is not None:
            return bp
        for ext in (".onnx", ".tflite"):
            cand = models_dir() / f"{value}{ext}"
            if cand.exists():
                return cand
        return p  # let the engine raise a clear "not found" with the literal value

    # No model configured: prefer a user-installed default, else the bundled one.
    installed = models_dir() / "hey_claude.onnx"
    if installed.exists():
        return installed
    bp = bundled_path("hey_claude")
    return bp if bp is not None else installed


def default_model_path() -> Path:
    return resolve_wakeword("")


@dataclass
class Config:
    # --- wake detection ---------------------------------------------------
    # "openwakeword" (default, low-power, needs a trained hey_claude.onnx) or
    # "whisper" (no model file; transcribes utterances and string-matches the
    # phrase — works out of the box but uses more CPU).
    engine: str = "openwakeword"
    wakeword_model: str = ""  # path to .onnx; "" => default_model_path()
    wake_phrase: str = "hey claude"  # spoken phrase (also used by the whisper engine)
    threshold: float = 0.5  # openWakeWord score in [0,1]; higher = fewer false positives
    refractory_seconds: float = 2.0  # ignore re-triggers within this window

    # --- command capture + transcription ----------------------------------
    samplerate: int = 16000
    mic_device: str = ""  # sounddevice device name/index; "" => system default
    silence_ms: int = 800  # trailing silence that ends the command
    max_command_seconds: float = 15.0  # hard cap so a stuck mic can't record forever
    preroll_ms: int = 300  # audio kept from just before speech starts (anti-clip)
    vad_start_rms: float = 0.012  # RMS above this counts as speech onset
    vad_keep_rms: float = 0.008  # RMS above this sustains an in-progress utterance
    whisper_model: str = "mlx-community/whisper-large-v3-turbo"  # command transcription
    whisper_wake_model: str = "mlx-community/whisper-tiny"  # used only by the whisper engine

    # --- launch -----------------------------------------------------------
    # "bg"       -> claude --bg "<command>"           (detached background agent)
    # "terminal" -> open a new Terminal running claude "<command>" (interactive)
    # "print"    -> claude -p "<command>" ...         (headless one-shot, logged)
    launch_mode: str = "bg"
    claude_bin: str = "claude"
    permission_mode: str = ""  # "", "acceptEdits", "plan", "bypassPermissions", ...
    claude_model: str = ""  # override the dispatched session's model; "" => default
    name_prefix: str = "hey-claude"  # background session name prefix
    max_concurrent: int = 0  # 0 = unlimited; otherwise refuse to dispatch past N live bg sessions
    confirm: bool = False  # print the command and require Enter before dispatching
    # Fully custom invocation, overriding launch_mode when non-empty. A shell-style
    # token list; these placeholders are substituted per-token (the {command} token
    # is passed as a single argument, never re-split, so nothing can be injected):
    #   {command} {name} {permission_mode} {model} {claude_bin}
    # e.g.  launch_template = 'claude --bg --name {name} --permission-mode acceptEdits {command}'
    launch_template: str = ""

    # --- feedback ---------------------------------------------------------
    chime: bool = True  # play sounds on wake / dispatch / cancel / error
    verbose: bool = True
    # Sound overrides — absolute paths to .aiff/.wav/.mp3 etc. Empty => built-in
    # macOS system sound. Set to "none" to silence just that one event.
    sound_wake: str = ""      # played when the wake word is detected
    sound_dispatch: str = ""  # played when an agent is dispatched
    sound_cancel: str = ""    # played when a wake fires but no command follows
    sound_error: str = ""     # played when dispatch fails

    # ---------------------------------------------------------------------
    def resolved_model_path(self) -> Path:
        return resolve_wakeword(self.wakeword_model)

    def to_toml(self) -> str:
        lines = [
            "# hey-claude configuration",
            f'# edit, or use: {APP_NAME} config set <key> <value>',
            "",
        ]
        for f in fields(self):
            lines.append(_toml_kv(f.name, getattr(self, f.name)))
        return "\n".join(lines) + "\n"

    @classmethod
    def load(cls) -> "Config":
        path = config_path()
        if not path.exists() or tomllib is None:
            return cls()
        with path.open("rb") as fh:
            data: dict[str, Any] = tomllib.load(fh)
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self) -> Path:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_toml(), encoding="utf-8")
        return path

    def set_field(self, key: str, raw: str) -> None:
        """Coerce a string CLI value to the field's declared type and assign it."""
        valid = {f.name: f for f in fields(self)}
        if key not in valid:
            raise KeyError(key)
        current = getattr(self, key)
        if isinstance(current, bool):
            value: Any = raw.strip().lower() in ("1", "true", "yes", "on")
        elif isinstance(current, int):
            value = int(raw)
        elif isinstance(current, float):
            value = float(raw)
        else:
            value = raw
        setattr(self, key, value)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _toml_kv(key: str, value: Any) -> str:
    if isinstance(value, bool):
        return f"{key} = {'true' if value else 'false'}"
    if isinstance(value, (int, float)):
        return f"{key} = {value}"
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'{key} = "{escaped}"'
