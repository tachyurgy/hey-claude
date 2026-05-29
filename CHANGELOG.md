# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to adhere
to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
