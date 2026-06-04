# Releases

Reverse-chronological deploy log for hey-claude. (Process details: `RELEASE.md`.)

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
