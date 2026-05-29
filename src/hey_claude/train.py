"""Helpers to obtain a "hey claude" openWakeWord model — without a microphone.

openWakeWord trains on 100% synthetic speech (Piper TTS), so you never record
anything and the result is speaker-independent. The fastest free path is the
official Colab notebook (~10 min on a free T4 GPU). When it finishes, download
the ``.onnx`` and drop it in with ``hey-claude import-model``.
"""

from __future__ import annotations

import shutil
import webbrowser
from pathlib import Path

from .config import Config, default_model_path, models_dir

COLAB_URL = (
    "https://colab.research.google.com/github/dscripka/openWakeWord/blob/main/"
    "notebooks/automatic_model_training.ipynb"
)
OWW_REPO = "https://github.com/dscripka/openWakeWord"
COMMUNITY_MODELS = "https://github.com/fwartner/home-assistant-wakewords-collection"


def guide(open_browser: bool = True) -> int:
    print("Train a free, on-device \"hey claude\" wake word — no microphone, no signup beyond Google.\n")
    print("1. Open the official openWakeWord training notebook (opening in your browser):")
    print(f"     {COLAB_URL}")
    print("2. In the notebook, set the target phrase to:  hey claude")
    print("   Runtime → Change runtime type → T4 GPU, then Runtime → Run all.")
    print("   It synthesizes speech, augments it, and trains a tiny classifier (~10 min).")
    print("3. Download the resulting  hey_claude.onnx  when the notebook finishes.")
    print("4. Install it here:")
    print("     hey-claude import-model ~/Downloads/hey_claude.onnx\n")
    print(f"Reference: {OWW_REPO}")
    print(f"Pre-trained community wake words (if one fits): {COMMUNITY_MODELS}\n")
    print("Prefer no model at all? The fallback engine works immediately:")
    print("     hey-claude config set engine whisper")
    if open_browser:
        try:
            webbrowser.open(COLAB_URL)
        except Exception:
            pass
    return 0


def _phrase_from_name(name: str) -> str:
    return name.replace("_", " ").replace("-", " ").strip()


def import_model(src: str, name: str = "", activate: bool = True) -> int:
    source = Path(src).expanduser()
    if not source.exists():
        print(f"✗ no such file: {source}")
        return 1
    if source.suffix.lower() not in (".onnx", ".tflite"):
        print(f"✗ expected a .onnx or .tflite model, got {source.suffix!r}")
        return 1
    stem = name or source.stem
    dest = models_dir() / f"{stem}{source.suffix.lower()}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    print(f"✓ installed wake-word model → {dest}")
    if activate:
        use_model(stem)
    else:
        print(f"  activate it with:  hey-claude models use {stem}")
    return 0


def use_model(name: str) -> int:
    """Make an installed model the active wake word and set the matching phrase."""
    md = models_dir()
    cand = md / name
    if not cand.exists():
        for ext in (".onnx", ".tflite"):
            if (md / f"{name}{ext}").exists():
                cand = md / f"{name}{ext}"
                break
    if not cand.exists():
        print(f"✗ no installed model named {name!r}. See: hey-claude models")
        return 1
    cfg = Config.load()
    cfg.wakeword_model = str(cand)
    cfg.wake_phrase = _phrase_from_name(cand.stem)
    cfg.engine = "openwakeword"
    cfg.save()
    print(f'✓ active wake word: "{cfg.wake_phrase}"  ({cand.name})')
    print("  start listening with:  hey-claude")
    return 0


def list_models() -> int:
    md = models_dir()
    active = str(Config.load().resolved_model_path())
    print(f"models directory: {md}")
    if md.exists():
        found = sorted(p for p in md.glob("*") if p.suffix.lower() in (".onnx", ".tflite"))
        if found:
            for p in found:
                marker = "  ← active" if str(p) == active else ""
                print(f'  • {p.stem:<16} "{_phrase_from_name(p.stem)}"{marker}')
        else:
            print("  (no wake-word models installed)")
    else:
        print("  (directory does not exist yet)")
    print(f"\nActivate one:        hey-claude models use <name>")
    print(f"Train one:           hey-claude train")
    print(f"Community models:    {COMMUNITY_MODELS}")
    return 0
