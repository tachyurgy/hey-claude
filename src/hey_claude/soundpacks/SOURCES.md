# Soundpack sources & licenses

Two origins: CC0 sound-effects, and the five spoken character voices.

## SFX packs — Kenney (CC0 1.0, public domain)

`clicks`, `metal`, `thud` are built from **Kenney** audio packs, released under
**Creative Commons CC0 1.0** (https://creativecommons.org/publicdomain/zero/1.0/) —
public domain, no attribution required.

- Source: https://kenney.nl/assets/category:Audio
- Built by `scripts/build_sfx_packs.py`

## Character voices — Hume Octave

The five character voices — `sawyer` (warm Southern campfire narrator, *default*),
`alastair` (precise British robo-butler), `mara` (mysterious wayfarer), `cass`
(brisk field scout), `sol` (dry deadpan night-desk) — are speech generated with
**Hume Octave** TTS. Each cue ships several distinct lines that shuffle on
playback, so a character speaks its whole range rather than one stock phrase.

| pack       | Hume voice                          |
|------------|-------------------------------------|
| `sawyer`    | Campfire Narrator                   |
| `alastair` | Fastidious Robo-Butler              |
| `mara`     | Mysterious Woman                    |
| `cass`     | Sitcom Girl                         |
| `sol`      | Unserious Movie Trailer Narrator    |

> **Redistribution note:** these clips are Hume Octave generations. Use/redistribution
> of the generated audio is governed by Hume's terms for the account that produced
> them (https://www.hume.ai/terms-of-use). Confirm those terms cover bundling the
> audio in this package before publishing a release. Anyone who prefers not to rely
> on them can switch to the CC0 SFX packs (`clicks`/`metal`/`thud`) or drop in their
> own voice with `hey-claude sounds new <name>`.

The full line matrix and the regenerator live alongside the project assets
(`phrases.json` / `gen_hume.py`).

## Normalization

Cues are leveled to a common loudness (RMS target with a true-peak ceiling) by
`scripts/_audio_norm.py`, so no pack is louder than another.

## The studio fallback

`studio` (the bundled `../earcons/*.wav`) is original synthesized work
(`scripts/gen_earcons.py`); it's the silent fallback for any event a pack omits.
