#!/usr/bin/env python3
"""Generate hey-claude's bundled earcons (the wake / endpoint / dispatch / cancel
/ error cues).

These are synthesized from scratch — soft sine partials with a fast attack and a
smooth exponential decay — so they read as a deliberate, "premium" UI sound set
rather than the raw macOS system beeps. Re-run to regenerate:

    python scripts/gen_earcons.py

Output: src/hey_claude/earcons/*.wav  (44.1 kHz, 16-bit mono, committed as
package data and shipped in the wheel).
"""

from __future__ import annotations

import struct
import wave
from pathlib import Path

import numpy as np

SR = 44100
OUT = Path(__file__).resolve().parent.parent / "src" / "hey_claude" / "earcons"

# Equal-tempered pitches we draw from (Hz).
A5, B5 = 880.00, 987.77
C6, Cs6, D6, E6, Fs6, G6, A6 = 1046.50, 1108.73, 1174.66, 1318.51, 1479.98, 1567.98, 1760.00
E4, A3, F3, D3 = 329.63, 220.00, 174.61, 146.83


def tone(freq, dur, *, amp=1.0, partials=(1.0, 0.22, 0.08), attack=0.006,
         decay=None, bell=False):
    """One note: summed harmonic partials under a fast-attack / exp-decay envelope.

    ``bell=True`` adds faint inharmonic partials for a struck-chime shimmer.
    """
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    sig = np.zeros(n)
    for i, pa in enumerate(partials, start=1):
        sig += pa * np.sin(2 * np.pi * freq * i * t)
    if bell:
        for mult, pa in ((2.76, 0.10), (5.40, 0.04)):
            sig += pa * np.sin(2 * np.pi * freq * mult * t) * np.exp(-t / (dur * 0.25))
    env = np.exp(-t / ((decay or dur) / 3.2))
    a = max(1, int(SR * attack))
    env[:a] *= np.linspace(0, 1, a)
    return amp * sig * env


def mix(*layers):
    """Overlay (offset_s, samples) layers into one buffer."""
    length = max(int(off * SR) + len(s) for off, s in layers)
    buf = np.zeros(length)
    for off, s in layers:
        i = int(off * SR)
        buf[i:i + len(s)] += s
    return buf


def normalize(buf, peak=0.32):
    m = np.max(np.abs(buf)) or 1.0
    buf = buf / m * peak
    # 4 ms click-free tail.
    f = max(1, int(0.004 * SR))
    buf[-f:] *= np.linspace(1, 0, f)
    return buf


def write(name, buf):
    OUT.mkdir(parents=True, exist_ok=True)
    data = (np.clip(buf, -1, 1) * 32767).astype("<i2")
    with wave.open(str(OUT / f"{name}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(s)) for s in data))
    print(f"  wrote {name}.wav  ({len(buf) / SR * 1000:.0f} ms)")


def build():
    # wake — "I'm listening, go ahead." A soft rising perfect fifth (C6→G6).
    write("wake", normalize(mix(
        (0.000, tone(C6, 0.18)),
        (0.085, tone(G6, 0.22)),
    )))

    # endpoint — "got it, stopped listening." One warm mid note, quick.
    write("endpoint", normalize(mix(
        (0.0, tone(D6, 0.15, decay=0.12)),
    ), peak=0.28))

    # dispatch — "sent." A bright ascending major triad, bell-like, ringing out.
    write("dispatch", normalize(mix(
        (0.000, tone(C6, 0.42, bell=True)),
        (0.070, tone(E6, 0.42, bell=True)),
        (0.140, tone(G6, 0.52, bell=True)),
    )))

    # cancel — "nothing happened." A gentle descending step, low and soft.
    write("cancel", normalize(mix(
        (0.000, tone(E6, 0.16)),
        (0.110, tone(A5, 0.22)),
    ), peak=0.26))

    # error — "that failed." Two soft low pulses, serious but not harsh.
    write("error", normalize(mix(
        (0.000, tone(A3, 0.20, partials=(1.0, 0.3, 0.12))),
        (0.180, tone(F3, 0.30, partials=(1.0, 0.3, 0.12))),
    ), peak=0.34))


if __name__ == "__main__":
    print(f"Generating earcons → {OUT}")
    build()
    print("done.")
