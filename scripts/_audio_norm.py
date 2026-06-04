"""Shared audio helper: normalize every cue to one consistent loudness.

The library mixes ultra-short clicks (sub-400 ms) with second-long spoken lines
and musical stings. EBU R128 loudnorm is undefined for the short transients
(integrated loudness measures as -inf), so we use **RMS normalization with a
true-peak ceiling** instead: measure each file's mean (RMS) and max level, push
the RMS to a common target, but never let the peak clip. This gives one even
perceived loudness across the whole set — clicks no longer wildly quieter or
louder than a voice pack. Output is 44.1 kHz / 16-bit mono WAV.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

TARGET_RMS_DB = -20.0   # common loudness target (mean volume)
PEAK_CEIL_DB = -1.5     # never let a peak exceed this (headroom, no clipping)
MAX_GAIN_DB = 30.0      # don't amplify near-silence into noise


def _measure(src: Path) -> tuple[float, float] | None:
    """Return (mean_volume_db, max_volume_db) via ffmpeg volumedetect."""
    proc = subprocess.run(
        ["ffmpeg", "-i", str(src), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    mean = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB", proc.stderr)
    peak = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?) dB", proc.stderr)
    if not mean or not peak:
        return None
    return float(mean.group(1)), float(peak.group(1))


def loudnorm(src: Path, dst: Path) -> bool:
    """Normalize ``src`` → ``dst`` (mono 44.1k/16-bit WAV) to TARGET_RMS_DB,
    clamped so the peak stays under PEAK_CEIL_DB. Returns success."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    stats = _measure(src)
    if stats is None:
        gain = 0.0
    else:
        mean_db, _max_db = stats
        # Push RMS to the common target; the limiter (below) catches any peaks,
        # so high-crest sounds (a bell, a clap) still reach the same loudness
        # instead of being held back by their transient peak.
        gain = max(-MAX_GAIN_DB, min(TARGET_RMS_DB - mean_db, MAX_GAIN_DB))
    af = f"volume={gain:.2f}dB,alimiter=limit={10 ** (PEAK_CEIL_DB / 20):.4f}"
    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-af", af,
         "-ar", "44100", "-ac", "1", "-sample_fmt", "s16",
         str(dst), "-loglevel", "error"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(f"    ✗ normalize {src.name}: {proc.stderr.strip()[:140]}", file=sys.stderr)
        return False
    return True
