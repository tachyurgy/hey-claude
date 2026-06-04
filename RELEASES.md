# Releases

Reverse-chronological deploy log for hey-claude. (Process details: `RELEASE.md`.)

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
- **NOT yet live (needs account-side setup, unchanged from v0.1.0):**
  - **PyPI** — Trusted Publishing wired; the release workflow runs but the upload
    step no-ops until a one-time trusted-publisher registration on pypi.org
    (owner=tachyurgy, repo=hey-claude, workflow=pypi-publish.yml; register as a
    *pending* publisher for the first upload). Then re-run the workflow.
  - **Homebrew** — `tachyurgy/homebrew-tap` must be made **public** and the formula
    `packaging/homebrew/hey-claude.rb` copied to `Formula/hey-claude.rb` there.
  - **Licensing note:** the package now bundles Hume Octave voice clips; confirm
    Hume's TOS covers redistribution before the public PyPI/Homebrew push (the CC0
    SFX packs are the safe fallback). See `src/hey_claude/soundpacks/SOURCES.md`.

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
