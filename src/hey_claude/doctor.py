"""Environment + readiness check. ``hey-claude doctor`` is the first-run wizard.

Each check prints a status line and, on failure, the exact command to fix it.
Returns 0 when everything required for the configured engine is in place.
"""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
import sys

from .config import Config, config_path, default_model_path

OK = "✓"
WARN = "⚠"
BAD = "✗"

MIN_CLAUDE = (2, 1, 139)  # claude --bg / agent view require this


class _Report:
    def __init__(self) -> None:
        self.failed = False

    def ok(self, label: str, detail: str = "") -> None:
        print(f"  {OK} {label}" + (f" — {detail}" if detail else ""))

    def warn(self, label: str, detail: str = "") -> None:
        print(f"  {WARN} {label}" + (f" — {detail}" if detail else ""))

    def bad(self, label: str, detail: str = "") -> None:
        self.failed = True
        print(f"  {BAD} {label}" + (f" — {detail}" if detail else ""))


def _claude_version(claude_bin: str) -> tuple[int, ...] | None:
    try:
        out = subprocess.run([claude_bin, "--version"], capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", out)
    return tuple(int(x) for x in m.groups()) if m else None


def run(cfg: Config) -> int:
    r = _Report()
    print("hey-claude doctor\n")

    # Platform
    if sys.platform != "darwin":
        r.bad("macOS", f"this tool targets macOS (found {sys.platform})")
    elif platform.machine() != "arm64":
        r.warn("Apple Silicon", f"found {platform.machine()}; MLX Whisper needs arm64")
    else:
        r.ok("Apple Silicon macOS", platform.mac_ver()[0])

    # Python
    v = sys.version_info
    if (3, 10) <= (v.major, v.minor) < (3, 14):
        r.ok("Python", f"{v.major}.{v.minor}.{v.micro}")
    else:
        r.warn("Python", f"{v.major}.{v.minor} (recommended: 3.12; <3.14 for ML wheels)")

    # claude CLI
    claude_bin = shutil.which(cfg.claude_bin or "claude")
    if not claude_bin:
        r.bad("claude on PATH", "install Claude Code, or set `claude_bin`")
    else:
        ver = _claude_version(claude_bin)
        if ver is None:
            r.warn("claude", f"found at {claude_bin}, version unknown")
        elif ver < MIN_CLAUDE:
            r.bad("claude version", f"{'.'.join(map(str, ver))} < {'.'.join(map(str, MIN_CLAUDE))} "
                                    "(run `claude update` for --bg / agent view)")
        else:
            r.ok("claude", f"{'.'.join(map(str, ver))} at {claude_bin}")

    # sounddevice / PortAudio / mic
    try:
        import sounddevice as sd  # noqa: PLC0415
        inputs = [d for d in sd.query_devices() if d.get("max_input_channels", 0) > 0]
        if inputs:
            try:
                default_idx = sd.default.device[0]
                default_name = sd.query_devices(default_idx)["name"] if default_idx is not None else inputs[0]["name"]
            except Exception:
                default_name = inputs[0]["name"]
            r.ok("microphone", f"{len(inputs)} input device(s); default: {default_name}")
        else:
            r.bad("microphone", "no input devices found")
    except OSError:
        r.bad("PortAudio", "brew install portaudio")
    except ModuleNotFoundError:
        r.bad("sounddevice", "pip install sounddevice")

    # MLX Whisper
    try:
        import mlx_whisper  # noqa: F401, PLC0415
        r.ok("mlx-whisper", "command transcription ready")
    except ModuleNotFoundError:
        r.bad("mlx-whisper", "pip install mlx-whisper")

    # Engine-specific
    if cfg.engine == "openwakeword":
        try:
            import openwakeword  # noqa: F401, PLC0415
            r.ok("openwakeword", "installed")
        except ModuleNotFoundError:
            r.bad("openwakeword", "pip install openwakeword")
        model = cfg.resolved_model_path()
        if model.exists():
            r.ok("wake-word model", str(model))
        else:
            r.bad("wake-word model", f"missing {model} — run `hey-claude train` "
                                     "(or `hey-claude config set engine whisper`)")
    else:
        r.ok("engine", "whisper (no model file required)")

    # Config
    cp = config_path()
    r.ok("config", str(cp) if cp.exists() else f"{cp} (defaults; not yet written)")

    print()
    print("microphone permission: macOS only prompts a process with a stable identity.")
    print("  • running from Terminal: grant Terminal mic access on first prompt")
    print("  • running headless/at login: install the .app —  hey-claude app")
    print()
    from . import onboarding  # local import: keeps doctor import-light
    onboarding.print_tips(cfg)
    print()
    if r.failed:
        print(f"{BAD} not ready — resolve the ✗ items above.")
        return 1
    print(f"{OK} ready. Start with:  hey-claude")
    return 0
