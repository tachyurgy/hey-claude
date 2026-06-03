# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to adhere
to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Bundled wake words** — five openWakeWord models ship as package data
  (`hey_claude` default, plus `okay_claude`, `hey_computer`, `hey_assistant`,
  `hey_agent`), so the tool works the moment it's installed with no training
  step. `models` lists them with a "mileage may vary" note; `models use <name>`
  activates a bundled model by name.
- **Agent-agnostic dispatch** — `agent list/use/show` and a preset registry
  (`claude-bg`/`claude-terminal`/`claude-print`, plus `codex`/`aider`/`opencode`/
  `gemini` starting points). A wake can drive any agent CLI; the `claude` binary
  is only required when the active template references it.
- **Full teardown** — `uninstall --all` removes everything a package manager
  can't reach: the launchd agent, the config dir + trained wake-word models, and
  the `~/Applications` `.app` bundle. It confirms before deleting (skip with
  `-y`/`--yes`) and prints the two follow-ups it can't do for you — revoking the
  macOS mic grant and removing the package itself. Bare `uninstall` still removes
  only the launchd agent and now hints at `--all`.

### Changed
- `config.resolve_wakeword()` resolves an explicit path, a bundled name, or an
  installed model, falling back to the bundled `hey_claude` so a fresh install
  listens immediately.

## [0.1.0] — initial release

### Added
- On-device wake-word pipeline: openWakeWord → energy-VAD endpointing →
  MLX Whisper → `claude --bg "<command>"`.
- Two wake engines: `openwakeword` (default, low-power, needs a trained model)
  and `whisper` (no model file, works out of the box).
- Three launch modes (`bg`, `terminal`, `print`) plus a fully custom
  `launch_template` with safe per-token placeholder substitution.
- Configurable per-event sounds (`sound_wake`/`dispatch`/`cancel`/`error`),
  accepting a file path, a macOS system-sound name, or `none`.
- CLI: `run`, `doctor`, `train`, `import-model`, `models`, `app`, `config`, and
  launchd service commands (`install`/`uninstall`/`start`/`stop`/`status`).
- `.app` generator for a microphone-permission-stable identity.
- launchd user agent for listening at login.
- TOML configuration at `~/.config/hey-claude/config.toml`.
- Unit tests for wake matching, config persistence/coercion, and the
  launch-template no-injection guarantee; macOS CI on Python 3.11–3.13.

[Unreleased]: https://github.com/tachyurgy/hey-claude/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/tachyurgy/hey-claude/releases/tag/v0.1.0
