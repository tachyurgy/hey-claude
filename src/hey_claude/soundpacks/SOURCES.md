# Soundpack sources & licenses

All bundled audio is free to use and redistribute. Two origins:

## SFX packs — Kenney (CC0 1.0, public domain)

`clicks`, `metal`, `thud` are built from **Kenney** audio packs, released under
**Creative Commons CC0 1.0** (https://creativecommons.org/publicdomain/zero/1.0/) —
public domain, no attribution required. `announcer` / `narrator` are Kenney's
spoken "Voiceover Pack" (male / female, also CC0).

- Source: https://kenney.nl/assets/category:Audio
- Built by `scripts/build_sfx_packs.py`

## Voice packs — Coqui VCTK-VITS (CC BY 4.0)

The neural voice packs — `sleepy`, `butler`, `buddy`, `captain`, `nadia`,
`cheery`, `chill`, `pro`, `soft`, `hype`, `crisp`, `scientist`, `coach`, `warm`,
`terse` — are generated **on-device** with Coqui TTS (`tts_models/en/vctk/vits`).
No TTS web demos were scraped; nothing proprietary is redistributed.

The voices come from the **VCTK corpus**, licensed **CC BY 4.0**
(https://creativecommons.org/licenses/by/4.0/) — © University of Edinburgh, CSTR.
Attribution: *CSTR VCTK Corpus, The Centre for Speech Technology Research,
University of Edinburgh.*

- Built by `scripts/gen_tts_packs.py`

## Normalization

Every cue is normalized to a common loudness (RMS target with a true-peak
ceiling) by `scripts/_audio_norm.py`, so no pack is louder than another.

## The studio fallback

`studio` (the bundled `../earcons/*.wav`) is original synthesized work
(`scripts/gen_earcons.py`); it's the silent fallback for any event a pack omits.
