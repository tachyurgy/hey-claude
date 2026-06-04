#!/usr/bin/env python3
"""Build hey-claude soundpacks from Kenney's **CC0 (public-domain)** audio packs.

Why CC0 and not just "royalty-free": this package is published publicly (PyPI +
Homebrew tap), so the bundled audio has to be redistributable *as files inside
the repo*. CC0 is true public domain — no attribution, no redistribution clause.
Kenney's audio packs are all CC0. (Pixabay/Mixkit "free" licenses forbid
redistributing the raw files standalone, so they're out for bundling.)

What it does:
  1. downloads + extracts the 10 Kenney audio zips (cached in $STAGE),
  2. maps hand-picked sounds to the five hey-claude events per themed pack,
  3. converts the chosen OGGs to 44.1 kHz/16-bit mono WAV via ffmpeg,
  4. writes them to src/hey_claude/soundpacks/<pack>/<event>[-<n>].wav.

Multiple files for one event (e.g. wake, wake-2) become rotating variants.
Re-run any time:  python scripts/build_sfx_packs.py
Source attributions (not required by CC0, kept for honesty): src/hey_claude/soundpacks/SOURCES.md
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _audio_norm import loudnorm  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "src" / "hey_claude" / "soundpacks"
STAGE = Path(os.environ.get("HC_SFX_STAGE", "/tmp/hc_sfx_stage"))
UNZ = STAGE / "unz"

# Kenney CC0 packs — (staging name, download URL). The hash in each URL is
# Kenney's cache-buster; refresh from the asset page if a link 404s.
KENNEY = {
    "interface-sounds": "https://kenney.nl/media/pages/assets/interface-sounds/fa43c1dd4d-1677589452/kenney_interface-sounds.zip",
    "ui-audio":         "https://kenney.nl/media/pages/assets/ui-audio/490d233f68-1677590494/kenney_ui-audio.zip",
    "digital-audio":    "https://kenney.nl/media/pages/assets/digital-audio/216eac4753-1677590265/kenney_digital-audio.zip",
    "sci-fi-sounds":    "https://kenney.nl/media/pages/assets/sci-fi-sounds/6b296f9ecf-1677589334/kenney_sci-fi-sounds.zip",
    "impact-sounds":    "https://kenney.nl/media/pages/assets/impact-sounds/87b4ddecda-1677589768/kenney_impact-sounds.zip",
    "rpg-audio":        "https://kenney.nl/media/pages/assets/rpg-audio/8e99002d76-1677590336/kenney_rpg-audio.zip",
    "casino-audio":     "https://kenney.nl/media/pages/assets/casino-audio/2472606a04-1721639069/kenney_casino-audio.zip",
    "music-jingles":    "https://kenney.nl/media/pages/assets/music-jingles/f37e530b9e-1677590399/kenney_music-jingles.zip",
    "voiceover-pack":   "https://kenney.nl/media/pages/assets/voiceover-pack/3f7f168698-1677589897/kenney_voiceover-pack.zip",
    "voiceover-fighter": "https://kenney.nl/media/pages/assets/voiceover-pack-fighter/6ceb77c6f1-1677589837/kenney_voiceover-pack-fighter.zip",
}

# Each pack: description + per-event source files (paths relative to UNZ, no ext).
# A list of >1 for an event => rotating variants (wake, wake-2, …).
EVENTS = ("wake", "endpoint", "dispatch", "cancel", "error")


def _jingles(prefix: str, sub: str) -> dict:
    base = f"music-jingles/Audio/{sub}/jingles_{prefix}"
    return {
        "wake":     [f"{base}00", f"{base}03"],
        "endpoint": [f"{base}05"],
        "dispatch": [f"{base}10"],
        "cancel":   [f"{base}07"],
        "error":    [f"{base}13"],
    }


def _voice(folder: str) -> dict:
    b = f"voiceover-pack/{folder}"
    return {
        "wake":     [f"{b}/ready", f"{b}/go"],
        "endpoint": [f"{b}/set"],
        "dispatch": [f"{b}/mission_completed"],
        "cancel":   [f"{b}/time_over"],
        "error":    [f"{b}/game_over"],
    }


PACKS: dict[str, tuple[str, dict]] = {
    "clicks": ("Clean UI clicks — crisp, minimal, modern interface.", {
        "wake":     ["interface-sounds/Audio/select_001", "interface-sounds/Audio/select_005"],
        "endpoint": ["interface-sounds/Audio/tick_002"],
        "dispatch": ["interface-sounds/Audio/confirmation_001"],
        "cancel":   ["interface-sounds/Audio/back_001"],
        "error":    ["interface-sounds/Audio/error_004"],
    }),
    "switches": ("Chunky toggle switches — tactile, mechanical UI.", {
        "wake":     ["ui-audio/Audio/switch1", "ui-audio/Audio/switch7"],
        "endpoint": ["ui-audio/Audio/rollover1"],
        "dispatch": ["ui-audio/Audio/switch20"],
        "cancel":   ["ui-audio/Audio/switch30"],
        "error":    ["ui-audio/Audio/switch16"],
    }),
    "digital": ("Retro digital blips — power-ups, tones, zaps.", {
        "wake":     ["digital-audio/Audio/highUp", "digital-audio/Audio/pepSound1"],
        "endpoint": ["digital-audio/Audio/tone1"],
        "dispatch": ["digital-audio/Audio/powerUp1"],
        "cancel":   ["digital-audio/Audio/lowDown"],
        "error":    ["digital-audio/Audio/zapThreeToneDown"],
    }),
    "scifi": ("Spaceship console — lasers, force fields, computer.", {
        "wake":     ["sci-fi-sounds/Audio/forceField_000", "sci-fi-sounds/Audio/laserSmall_000"],
        "endpoint": ["sci-fi-sounds/Audio/computerNoise_000"],
        "dispatch": ["sci-fi-sounds/Audio/laserRetro_000"],
        "cancel":   ["sci-fi-sounds/Audio/doorClose_000"],
        "error":    ["sci-fi-sounds/Audio/lowFrequency_explosion_000"],
    }),
    "casino": ("Casino table — chips, cards, dice.", {
        "wake":     ["casino-audio/Audio/chip-lay-1", "casino-audio/Audio/card-slide-1"],
        "endpoint": ["casino-audio/Audio/chips-stack-1"],
        "dispatch": ["casino-audio/Audio/chips-collide-1"],
        "cancel":   ["casino-audio/Audio/card-shove-1"],
        "error":    ["casino-audio/Audio/dice-throw-1"],
    }),
    "impact": ("Physical impacts — glass, bell, wood, metal taps.", {
        "wake":     ["impact-sounds/Audio/impactGlass_light_000", "impact-sounds/Audio/impactGeneric_light_000"],
        "endpoint": ["impact-sounds/Audio/impactTin_medium_000"],
        "dispatch": ["impact-sounds/Audio/impactBell_heavy_000"],
        "cancel":   ["impact-sounds/Audio/impactSoft_medium_000"],
        "error":    ["impact-sounds/Audio/impactWood_heavy_000"],
    }),
    "fantasy": ("RPG inventory — leather, coins, cloth, creaks.", {
        "wake":     ["rpg-audio/Audio/metalClick", "rpg-audio/Audio/handleSmallLeather"],
        "endpoint": ["rpg-audio/Audio/cloth1"],
        "dispatch": ["rpg-audio/Audio/handleCoins"],
        "cancel":   ["rpg-audio/Audio/bookClose"],
        "error":    ["rpg-audio/Audio/creak1"],
    }),
    "jingles-steel":     ("Steel-drum jingles — bright, tropical musical stings.", _jingles("STEEL", "Steel jingles")),
    "jingles-pizzicato": ("Pizzicato strings — plucked, playful musical stings.", _jingles("PIZZI", "Pizzicato jingles")),
    "jingles-sax":       ("Saxophone jingles — warm, jazzy musical stings.", _jingles("SAX", "Sax jingles")),
    "chiptune":          ("8-bit NES jingles — classic video-game fanfares.", _jingles("NES", "8-Bit jingles")),
    "jingles-hit":       ("Orchestral hits — punchy cinematic stabs.", _jingles("HIT", "Hit jingles")),
    "announcer": ("Game announcer (male) — \"ready\", \"go\", \"mission completed\".", _voice("Male")),
    "narrator":  ("Game narrator (female) — \"ready\", \"go\", \"mission completed\".", _voice("Female")),
    "fighter": ("Arcade fight announcer — \"ready\", \"fight\", \"flawless victory\".", {
        "wake":     ["voiceover-fighter/Audio/ready", "voiceover-fighter/Audio/begin"],
        "endpoint": ["voiceover-fighter/Audio/fight"],
        "dispatch": ["voiceover-fighter/Audio/flawless_victory"],
        "cancel":   ["voiceover-fighter/Audio/tie"],
        "error":    ["voiceover-fighter/Audio/game_over"],
    }),
    # --- second batch: 10 more, carved from different sound families ---------
    "lasers": ("Laser blasters — pew-pew arcade shooter.", {
        "wake":     ["digital-audio/Audio/laser1", "digital-audio/Audio/laser5"],
        "endpoint": ["digital-audio/Audio/laser3"],
        "dispatch": ["digital-audio/Audio/zapTwoTone"],
        "cancel":   ["digital-audio/Audio/phaserDown1"],
        "error":    ["digital-audio/Audio/laser8"],
    }),
    "engines": ("Starship engines — thrusters, drives, low hum.", {
        "wake":     ["sci-fi-sounds/Audio/thrusterFire_000", "sci-fi-sounds/Audio/spaceEngineSmall_000"],
        "endpoint": ["sci-fi-sounds/Audio/engineCircular_000"],
        "dispatch": ["sci-fi-sounds/Audio/spaceEngine_000"],
        "cancel":   ["sci-fi-sounds/Audio/spaceEngineLow_000"],
        "error":    ["sci-fi-sounds/Audio/lowFrequency_explosion_001"],
    }),
    "airlock": ("Sci-fi doors — airlocks, force fields, latches.", {
        "wake":     ["sci-fi-sounds/Audio/doorOpen_000", "sci-fi-sounds/Audio/doorOpen_001"],
        "endpoint": ["sci-fi-sounds/Audio/doorClose_001"],
        "dispatch": ["sci-fi-sounds/Audio/forceField_001"],
        "cancel":   ["sci-fi-sounds/Audio/doorClose_002"],
        "error":    ["sci-fi-sounds/Audio/impactMetal_000"],
    }),
    "metal": ("Metal & bells — clanks, plates, struck tin.", {
        "wake":     ["impact-sounds/Audio/impactMetal_light_000", "impact-sounds/Audio/impactTin_medium_000"],
        "endpoint": ["impact-sounds/Audio/impactMetal_medium_000"],
        "dispatch": ["impact-sounds/Audio/impactBell_heavy_001"],
        "cancel":   ["impact-sounds/Audio/impactPlate_light_000"],
        "error":    ["impact-sounds/Audio/impactMetal_heavy_000"],
    }),
    "thud": ("Soft thuds — muted body-blow impacts, low and physical.", {
        "wake":     ["impact-sounds/Audio/impactPunch_medium_000", "impact-sounds/Audio/impactSoft_medium_001"],
        "endpoint": ["impact-sounds/Audio/impactSoft_medium_000"],
        "dispatch": ["impact-sounds/Audio/impactPunch_heavy_000"],
        "cancel":   ["impact-sounds/Audio/impactSoft_heavy_000"],
        "error":    ["impact-sounds/Audio/impactPunch_heavy_003"],
    }),
    "cards": ("Card table — slides, fans, shuffles, deals.", {
        "wake":     ["casino-audio/Audio/card-slide-2", "casino-audio/Audio/card-fan-1"],
        "endpoint": ["casino-audio/Audio/card-place-1"],
        "dispatch": ["casino-audio/Audio/cards-pack-open-1"],
        "cancel":   ["casino-audio/Audio/card-shove-2"],
        "error":    ["casino-audio/Audio/card-shuffle"],
    }),
    "dice": ("Dice — grabs, shakes, rolls, throws.", {
        "wake":     ["casino-audio/Audio/dice-grab-1", "casino-audio/Audio/dice-shake-1"],
        "endpoint": ["casino-audio/Audio/dice-shake-2"],
        "dispatch": ["casino-audio/Audio/dice-throw-2"],
        "cancel":   ["casino-audio/Audio/die-throw-1"],
        "error":    ["casino-audio/Audio/dice-throw-3"],
    }),
    "books": ("Library — page flips, book opens/closes, creaks.", {
        "wake":     ["rpg-audio/Audio/bookOpen", "rpg-audio/Audio/bookFlip1"],
        "endpoint": ["rpg-audio/Audio/bookFlip2"],
        "dispatch": ["rpg-audio/Audio/bookPlace1"],
        "cancel":   ["rpg-audio/Audio/bookClose"],
        "error":    ["rpg-audio/Audio/creak2"],
    }),
    "blades": ("Blades — knives drawn, slices, metal clicks.", {
        "wake":     ["rpg-audio/Audio/drawKnife1", "rpg-audio/Audio/metalClick"],
        "endpoint": ["rpg-audio/Audio/drawKnife2"],
        "dispatch": ["rpg-audio/Audio/knifeSlice"],
        "cancel":   ["rpg-audio/Audio/handleSmallLeather2"],
        "error":    ["rpg-audio/Audio/chop"],
    }),
    "war": ("Tactical squad (voice) — \"go go go\", \"reloading\", \"fire in the hole\".", {
        "wake":     ["voiceover-pack/Male/war_go_go_go", "voiceover-pack/Male/war_cover_me"],
        "endpoint": ["voiceover-pack/Male/war_reloading"],
        "dispatch": ["voiceover-pack/Male/war_fire_in_the_hole"],
        "cancel":   ["voiceover-pack/Male/war_medic"],
        "error":    ["voiceover-pack/Male/war_look_out"],
    }),
}


def fetch_and_extract() -> None:
    (STAGE / "zips").mkdir(parents=True, exist_ok=True)
    UNZ.mkdir(parents=True, exist_ok=True)
    for name, url in KENNEY.items():
        if (UNZ / name).is_dir():
            continue
        zp = STAGE / "zips" / f"{name}.zip"
        if not zp.exists():
            print(f"  ↓ {name}")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as r, zp.open("wb") as f:
                shutil.copyfileobj(r, f)
        with zipfile.ZipFile(zp) as z:
            z.extractall(UNZ / name)


def find_src(rel: str) -> Path | None:
    """Resolve a relative (extensionless) source path to a real audio file."""
    for ext in (".ogg", ".wav", ".mp3"):
        p = UNZ / f"{rel}{ext}"
        if p.exists():
            return p
    return None


def convert(src: Path, dst: Path) -> bool:
    """Convert + **loudness-normalize** to a uniform level so every cue across
    every pack is the same perceived loudness (the old per-file levels were all
    over the place). Uses two-pass EBU R128 loudnorm via the shared helper."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    return loudnorm(src, dst)


def build(only: list[str] | None = None) -> None:
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found — brew install ffmpeg")
    print("Fetching CC0 source packs (cached in $HC_SFX_STAGE)…")
    fetch_and_extract()
    print(f"Building packs → {OUT}")
    missing = []
    items = [(p, v) for p, v in PACKS.items() if not only or p in only]
    for pack, (desc, mapping) in items:
        n = 0
        for event in EVENTS:
            for i, rel in enumerate(mapping.get(event, [])):
                src = find_src(rel)
                if src is None:
                    missing.append(f"{pack}/{event}: {rel}")
                    continue
                name = event if i == 0 else f"{event}-{i + 1}"
                if convert(src, OUT / pack / f"{name}.wav"):
                    n += 1
        print(f"  {pack:<18} {n} files  — {desc}")
    if missing:
        print("\n⚠ unresolved sources (skipped):")
        for m in missing:
            print(f"    {m}")
    write_sources()


def write_sources() -> None:
    lines = [
        "# Soundpack sources",
        "",
        "The non-synthesized soundpacks are built from **Kenney** audio packs,",
        "all released under **Creative Commons CC0 1.0 (public domain)** — free to",
        "use and redistribute, no attribution required. Listed here for honesty.",
        "",
        "Source: https://kenney.nl/assets/category:Audio  ·  License: https://creativecommons.org/publicdomain/zero/1.0/",
        "",
        "Built by `scripts/build_sfx_packs.py`. The synthesized packs (studio, etc.)",
        "are original work, see `scripts/gen_soundpacks.py`.",
        "",
    ]
    for pack, (desc, _) in PACKS.items():
        lines.append(f"- **{pack}** — {desc}")
    (OUT / "SOURCES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build(only=sys.argv[1:] or None)
    print("done.")
