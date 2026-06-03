# Releasing hey-claude

The source repo is **private** for now. When you're ready to launch (e.g. post to
Hacker News), flip both repos to public and cut a release. Steps below are the
exact commands; nothing here needs to run unattended.

## 0. Go public

```bash
gh repo edit tachyurgy/hey-claude --visibility public --accept-visibility-change-consequences
gh repo edit tachyurgy/homebrew-tap --visibility public --accept-visibility-change-consequences
```

A Homebrew tap **must be public** for `brew install` to work.

## 1. Tag and cut a GitHub release

```bash
cd ~/Desktop/hey-claude
git tag v0.1.0
git push origin v0.1.0
gh release create v0.1.0 --title "hey-claude v0.1.0" --generate-notes
```

## 2. Update the Homebrew formula with the real tarball hash

### Automatic (recommended)

`.github/workflows/release.yml` runs when you publish a release and opens a PR
against `tachyurgy/homebrew-tap` with the new version + sha256 already filled in.
It needs a one-time secret:

1. Create a fine-grained PAT with **Contents: read/write** on `tachyurgy/homebrew-tap`.
2. Add it to the **hey-claude** repo as a secret named `COMMITTER_TOKEN`
   (`gh secret set COMMITTER_TOKEN --repo tachyurgy/hey-claude`).

After `gh release create`, just merge the PR the workflow opens on the tap.

### Manual (fallback)

```bash
URL="https://github.com/tachyurgy/hey-claude/archive/refs/tags/v0.1.0.tar.gz"
SHA=$(curl -sL "$URL" | shasum -a 256 | awk '{print $1}')
echo "$SHA"
# In homebrew-tap/Formula/hey-claude.rb replace the placeholder sha256 with $SHA,
# commit, and push.
```

Then verify the formula installs cleanly:

```bash
brew tap tachyurgy/tap
brew install --build-from-source hey-claude
brew test hey-claude
brew audit --strict --online hey-claude   # before submitting anywhere
```

Users then install with:

```bash
brew install tachyurgy/tap/hey-claude
```

## 3. Publish to PyPI (needs your PyPI account + API token)

```bash
cd ~/Desktop/hey-claude
. .venv/bin/activate
pip install build twine
python -m build                      # writes dist/hey_claude-0.1.0{.tar.gz,-py3-none-any.whl}
twine check dist/*
twine upload dist/*                  # prompts for __token__ / your PyPI API token
```

After that:

```bash
pipx install hey-claude
# or
brew install portaudio && pip install hey-claude
```

> Tip: validate end-to-end on TestPyPI first —
> `twine upload --repository testpypi dist/*` then
> `pipx install --index-url https://test.pypi.org/simple/ hey-claude`.

## 4. Bump versions for later releases

Version lives in two spots — keep them in sync:

- `src/hey_claude/version.py` → `__version__`
- `pyproject.toml` → `[project] version`

Then repeat steps 1–3 with the new tag.

## Launch checklist (Hacker News / Show HN)

- [ ] Both repos public
- [ ] `v0.1.0` release with notes
- [ ] Bundled wake words land in the wheel: `python -m build --wheel` then
      `unzip -l dist/*.whl | grep models/.*onnx` shows all five `.onnx` files
- [ ] Fresh install listens with **no training step** (`hey-claude` just works);
      `hey-claude agent use codex` retargets the agent
- [ ] Formula sha256 updated; `brew install tachyurgy/tap/hey-claude` works on a clean machine
- [ ] `pip install hey-claude` works in a fresh 3.12 venv
- [ ] README GIF/asciinema of "Hey Claude, …" → a row appearing in `claude agents`
- [ ] `hey-claude doctor` output looks clean on a fresh setup
- [ ] **Deploy the Levelbrook site at the same time** so the cross-links resolve:
      the README + blog point at `github.com/tachyurgy/hey-claude` (404s until the
      repo is public), and the `~/Desktop/c2c/site` blog post + portfolio card are
      staged but **not deployed** — push the `consulting-levelbrook` Pages project
      so consulting.levelbrook.com/writing/hey-claude-on-device-wake-word/ goes live
