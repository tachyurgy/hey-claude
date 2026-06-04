#!/usr/bin/env python3
"""Generate the five character voice packs with Hume Octave TTS.

Reads ``scripts/voice_lines.json`` (the line matrix) and writes each line to the
matching soundpack folder under ``src/hey_claude/soundpacks/<pack>/``. Variant
index 1 is ``<event>.mp3``; later variants are ``<event>-2.mp3``, ``-3.mp3`` …,
which is exactly what ``sounds.pack_event_files`` rotates over.

Idempotent: existing non-empty files are skipped, so a rerun only fills gaps.

Usage:
    export HUME_API_KEY=...           # your Hume API key
    python3 scripts/gen_voice_packs.py            # all packs
    python3 scripts/gen_voice_packs.py sawyer sol  # only these packs
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MATRIX = Path(__file__).resolve().parent / "voice_lines.json"
PACKS = ROOT / "src" / "hey_claude" / "soundpacks"
EVENTS = ("wake", "endpoint", "dispatch", "cancel", "error")

API_KEY = os.environ.get("HUME_API_KEY", "").strip()


def variant_name(event: str, idx: int) -> str:
    return f"{event}.mp3" if idx == 1 else f"{event}-{idx}.mp3"


def synth(text: str, voice: str, out: Path) -> bool:
    """One Hume Octave generation -> a complete mp3 at ``out``. Returns success."""
    payload = json.dumps({
        "utterances": [{"text": text, "voice": {"name": voice, "provider": "HUME_AI"}, "speed": 1.0}],
        "format": {"type": "mp3"},
        "num_generations": 1,
    })
    for attempt in range(4):
        r = subprocess.run(
            ["curl", "-s", "-o", str(out), "-w", "%{http_code}",
             "-X", "POST", "https://api.hume.ai/v0/tts/file",
             "-H", "Content-Type: application/json",
             "-H", f"X-Hume-Api-Key: {API_KEY}",
             "-d", payload, "--max-time", "90"],
            capture_output=True, text=True, timeout=100,
        )
        code = r.stdout.strip()
        if code == "200" and out.exists() and out.stat().st_size > 0:
            return True
        out.unlink(missing_ok=True)
        if code == "429":  # rate limited — back off and retry
            time.sleep(8 * (attempt + 1))
            continue
        print(f"      FAIL (HTTP {code})", flush=True)
        return False
    return False


def main(argv: list[str]) -> int:
    if not API_KEY:
        print("Set HUME_API_KEY in the environment first.", file=sys.stderr)
        return 2
    data = json.loads(MATRIX.read_text())
    voices: dict[str, str] = data["voices"]
    lines: dict[str, dict[str, list[str]]] = data["lines"]
    only = set(argv[1:])
    ok = skip = fail = 0
    for pack, by_event in lines.items():
        if only and pack not in only:
            continue
        voice = voices[pack]
        dest = PACKS / pack
        dest.mkdir(parents=True, exist_ok=True)
        print(f"[{pack}]  voice={voice!r}", flush=True)
        for event in EVENTS:
            for idx, text in enumerate(by_event.get(event, []), start=1):
                out = dest / variant_name(event, idx)
                if out.exists() and out.stat().st_size > 0:
                    skip += 1
                    continue
                print(f"  {variant_name(event, idx):16} {text!r}", flush=True)
                if synth(text, voice, out):
                    ok += 1
                else:
                    fail += 1
                time.sleep(1.5)
    print(f"\n=== done: {ok} generated, {skip} skipped, {fail} failed ===")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
