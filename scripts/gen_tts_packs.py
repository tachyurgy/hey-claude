#!/usr/bin/env python3
"""Generate spoken-voice soundpacks with **local neural TTS** (Coqui VCTK-VITS).

Why this and not a TTS provider's web demo: scraping a paid demo's audio and
shipping it in a public package violates those demos' terms and isn't licensed
for redistribution. Coqui's VCTK-VITS model runs entirely on-device and the VCTK
voice corpus is **CC BY 4.0** — free to use and redistribute with attribution
(recorded in soundpacks/SOURCES.md). 109 distinct neural speakers, so each pack
is a different voice *saying different things* for each event.

Run with the interpreter that has Coqui TTS installed (the one behind `tts`):
    /opt/homebrew/opt/python@3.11/bin/python3.11 scripts/gen_tts_packs.py
(the model loads once, then all ~90 clips synth in one process). Every clip is
loudness-normalized to the same level as the rest of the library.
"""

from __future__ import annotations

import contextlib
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "src" / "hey_claude" / "soundpacks"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _audio_norm import loudnorm  # noqa: E402

MODEL = "tts_models/en/vctk/vits"

# (pack, speaker, description, {event: [phrases]}).  >1 phrase => rotating variants.
PERSONAS: list[tuple[str, str, str, dict]] = [
    ("assistant", "p225", "Polite assistant — \"Yes?\" · \"On it!\"", {
        "wake": ["Yes?", "How can I help?"], "endpoint": ["Let me see."],
        "dispatch": ["On it!"], "cancel": ["Never mind."], "error": ["Something went wrong."]}),
    ("butler", "p226", "Formal butler — \"You rang?\" · \"Right away.\"", {
        "wake": ["You rang?", "At your service."], "endpoint": ["Very good."],
        "dispatch": ["Right away."], "cancel": ["As you wish."], "error": ["I'm afraid that failed."]}),
    ("buddy", "p243", "Casual buddy — \"What's up?\" · \"On it.\"", {
        "wake": ["What's up?", "Yeah?"], "endpoint": ["Gotcha."],
        "dispatch": ["On it."], "cancel": ["No worries."], "error": ["Aw, that broke."]}),
    ("captain", "p254", "Ship captain — \"Report.\" · \"Engage.\"", {
        "wake": ["Report.", "Standing by."], "endpoint": ["Acknowledged."],
        "dispatch": ["Engage."], "cancel": ["Belay that."], "error": ["We have a problem."]}),
    ("android", "p270", "Flat AI — \"Listening.\" · \"Executing.\"", {
        "wake": ["Listening.", "Awaiting input."], "endpoint": ["Processing."],
        "dispatch": ["Executing."], "cancel": ["Aborted."], "error": ["Error detected."]}),
    ("cheery", "p228", "Upbeat helper — \"Hi there!\" · \"You got it!\"", {
        "wake": ["Hi there!", "Ready when you are!"], "endpoint": ["Got it!"],
        "dispatch": ["You got it!"], "cancel": ["All good!"], "error": ["Oops!"]}),
    ("chill", "p258", "Laid-back — \"Yeah?\" · \"On it.\"", {
        "wake": ["Yeah?", "I'm here."], "endpoint": ["Cool."],
        "dispatch": ["On it."], "cancel": ["It's fine."], "error": ["That didn't work."]}),
    ("pro", "p237", "Professional — \"Ready.\" · \"Dispatching now.\"", {
        "wake": ["Ready.", "Go ahead."], "endpoint": ["Understood."],
        "dispatch": ["Dispatching now."], "cancel": ["Cancelled."], "error": ["That failed."]}),
    ("soft", "p231", "Soft-spoken — \"Mm-hmm?\" · \"Done.\"", {
        "wake": ["Mm hmm?", "I'm listening."], "endpoint": ["Of course."],
        "dispatch": ["Done."], "cancel": ["Okay."], "error": ["Uh oh."]}),
    ("hype", "p245", "Hype man — \"Let's go!\" · \"Sending it!\"", {
        "wake": ["Let's go!", "Hit me!"], "endpoint": ["Yes!"],
        "dispatch": ["Sending it!"], "cancel": ["Nope!"], "error": ["Ah, dang!"]}),
    ("crisp", "p233", "Crisp secretary — \"Yes?\" · \"Right away.\"", {
        "wake": ["Yes?", "Go ahead."], "endpoint": ["Noted."],
        "dispatch": ["Right away."], "cancel": ["Disregard."], "error": ["There was an error."]}),
    ("scientist", "p246", "Curious scientist — \"Hmm?\" · \"Initiating.\"", {
        "wake": ["Hmm?", "Go on."], "endpoint": ["Interesting."],
        "dispatch": ["Initiating."], "cancel": ["Never mind."], "error": ["Anomaly detected."]}),
    ("coach", "p263", "Coach — \"Talk to me.\" · \"Let's do it.\"", {
        "wake": ["Talk to me.", "Let's hear it."], "endpoint": ["Good."],
        "dispatch": ["Let's do it."], "cancel": ["Shake it off."], "error": ["We missed that one."]}),
    ("warm", "p236", "Warm & kind — \"I'm here.\" · \"On it now.\"", {
        "wake": ["I'm here.", "Go ahead."], "endpoint": ["Of course."],
        "dispatch": ["On it now."], "cancel": ["That's okay."], "error": ["Oh no, it failed."]}),
    ("terse", "p256", "Minimalist — \"Yep.\" · \"Sent.\"", {
        "wake": ["Yep.", "Go."], "endpoint": ["Okay."],
        "dispatch": ["Sent."], "cancel": ["No."], "error": ["Failed."]}),
]

EVENTS = ("wake", "endpoint", "dispatch", "cancel", "error")


def main() -> int:
    try:
        from TTS.api import TTS
    except ModuleNotFoundError:
        sys.exit("Coqui TTS not importable — run with the python behind `tts` "
                 "(/opt/homebrew/opt/python@3.11/bin/python3.11).")
    print(f"Loading {MODEL} (once)…")
    with contextlib.redirect_stdout(open(os.devnull, "w")):
        tts = TTS(model_name=MODEL, progress_bar=False)
    print(f"Building {len(PERSONAS)} TTS packs → {OUT}")
    descs = {}
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for pack, speaker, desc, phrases in PERSONAS:
            descs[pack] = desc
            n = 0
            for event in EVENTS:
                for i, phrase in enumerate(phrases.get(event, [])):
                    raw = tmp / "raw.wav"
                    with contextlib.redirect_stdout(open(os.devnull, "w")):
                        tts.tts_to_file(text=phrase, speaker=speaker, file_path=str(raw))
                    name = event if i == 0 else f"{event}-{i + 1}"
                    if loudnorm(raw, OUT / pack / f"{name}.wav"):
                        n += 1
            print(f"  {pack:<11} {speaker}  {n} clips  — {desc}")
    append_sources(descs)
    print("done.")
    return 0


def append_sources(descs: dict) -> None:
    path = OUT / "SOURCES.md"
    block = [
        "",
        "## TTS voice packs (neural, on-device)",
        "",
        "Generated locally with **Coqui TTS** (`tts_models/en/vctk/vits`).",
        "Voices from the **VCTK** corpus — **CC BY 4.0** "
        "(https://creativecommons.org/licenses/by/4.0/), "
        "© University of Edinburgh CSTR. Built by `scripts/gen_tts_packs.py`.",
        "",
    ]
    for pack, desc in descs.items():
        block.append(f"- **{pack}** — {desc}")
    block.append("")
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    path.write_text(existing + "\n".join(block) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
