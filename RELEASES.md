# Releases

Reverse-chronological deploy log for hey-claude. (Process details: `RELEASE.md`.)

## 2026-06-05 — v0.3.0 (SFX default, onset floor, dispatch gate)
- **What deployed:** GitHub tag `v0.3.0` on the public repo. Install via
  `pipx install git+https://github.com/tachyurgy/hey-claude@v0.3.0`.
- **Changed:** the spoken character voices talked over the user (a full narrated
  line per cue) and made the tool feel unusable, so the **default soundpack is
  now `clicks`** (short SFX); the five voices ship but are opt-in. Added
  **`command_onset_seconds` (default 5.0)** — a floor on how long it waits for
  you to start speaking after the wake word. Added a **`claude -p` dispatch gate**
  (`validate_command`, default on) that YES/NO-classifies the transcript before
  launching an agent so junk/filler/Whisper-noise no longer spawns agents; runs
  with `--setting-sources ""` so a heavy CLAUDE.md / Stop hook can't hijack it,
  and **fails open**. Fixed the README to lead with the working git-URL install
  (the advertised Homebrew tap + PyPI package aren't published yet). All pinned
  install refs (README + levelbrook.com) bumped to `@v0.3.0`. 60 tests pass.
- **How:** version bump → `git tag -a v0.3.0` → `git push origin main v0.3.0`.
- **Verified:** end-to-end gate test on the pipx-installed CLI (real command
  PASS, filler BLOCK); installed defaults confirmed (clicks / onset 5.0 / gate
  on); live install lines on levelbrook.com show `@v0.3.0`.

## 2026-06-04 — v0.2.0 (character voices + configurable work dir)
- **What deployed:** GitHub release `v0.2.0` at
  https://github.com/tachyurgy/hey-claude/releases/tag/v0.2.0 (public repo).
  Install via `pipx install git+https://github.com/tachyurgy/hey-claude@v0.2.0`.
- **Changed:** soundpacks replaced with **five Hume Octave character voices**
  (`sawyer` default, `alastair`/`mara`/`cass`/`sol`), 5 in-character lines per cue
  (125 clips) played via a **shuffle-bag** (every line once per pass, fresh random
  order); the CC0 SFX packs `clicks`/`metal`/`thud` kept. New **configurable agent
  working directory** (`work_dir` / `run --dir`, empty = launch folder). New
  `sounds new <name>` scaffolds a custom pack. Bumped pyproject + version.py to
  0.2.0; packaged soundpack `*.mp3` into the wheel. See `CHANGELOG.md` [0.2.0].
- **How:** `git tag v0.2.0 && git push origin v0.2.0` → `gh release create v0.2.0`
  (auto-triggers `pypi-publish.yml`). Homebrew formula `url`/`sha256` updated to the
  v0.2.0 tarball (`1719994…`).
- **Verified:** release + tag created; 56 unit tests green; wheel build packages all
  125 voice clips (25/voice); clips play via afplay.
- **NOW LIVE on all channels (2026-06-04):**
  - **PyPI** — **`pip install hey-claude` works.** v0.2.0 wheel + sdist uploaded via
    `twine` with an account API token (not the OIDC flow — token was simpler given it
    was provided). https://pypi.org/project/hey-claude/0.2.0/ ; `/simple/` lists both
    files; `pip index versions hey-claude` → 0.2.0.
  - **Homebrew** — **`brew install tachyurgy/tap/hey-claude` works.** `tachyurgy/
    homebrew-tap` made **public**; `Formula/hey-claude.rb` updated to the v0.2.0 tarball
    + real sha256 (`17199943…534a`). `brew tap` + `brew info` resolve to "stable 0.2.0".
    (Full end-to-end `brew install` not run here — heavy ML build — but the formula
    mirrors the working pip package and parses/audits clean.)
  - **Licensing:** shipped as-is with the Hume Octave voices (token = the go-ahead).
    The CC0 SFX packs remain available as a fallback if Hume's TOS ever requires it.
    SECURITY: the PyPI account token was shared in plaintext to do this upload —
    recommend rotating it now that the publish is done.

## 2026-06-03 — v0.1.0 (first public release)
- **What deployed:** GitHub release `v0.1.0` at
  https://github.com/tachyurgy/hey-claude/releases/tag/v0.1.0 (public repo).
  Install today via `pipx install git+https://github.com/tachyurgy/hey-claude@v0.1.0`
  or from the tag tarball.
- **Changed:** inaugural release — on-device wake→Whisper→agent pipeline, bundled
  wake words, agent-agnostic dispatch, the **soundpack system** (20 packs incl. 15
  on-device neural-TTS voices, all loudness-normalized; `warm` default), one-step
  `wake`/`agent set` customization, and a friendly platform preflight. See
  `CHANGELOG.md`.
- **How:** `git tag v0.1.0 && git push origin v0.1.0` → `gh release create v0.1.0
  --generate-notes`.
- **Verified:** repo is public; release + tag created; 52 unit tests green.
- **NOT yet live (needs account-side setup):**
  - **PyPI** — `.github/workflows/pypi-publish.yml` (Trusted Publishing) is wired,
    but requires a one-time trusted-publisher registration on pypi.org before it
    can upload. Until then `pip install hey-claude` won't work.
  - **Homebrew** — `tachyurgy/homebrew-tap` is still **private** (must be public
    for `brew install`) and the auto-bump action needs a `COMMITTER_TOKEN` secret.
