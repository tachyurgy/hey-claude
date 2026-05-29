# Contributing

Thanks for your interest in `hey-claude`. It's a small, focused tool — a clean
PR that keeps it that way is very welcome.

## Setup

```bash
git clone https://github.com/tachyurgy/hey-claude
cd hey-claude
brew install portaudio
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Project layout

| Path | What |
|---|---|
| `src/hey_claude/audio.py` | mic capture + energy VAD endpointing |
| `src/hey_claude/wake.py` | wake engines + the pure-stdlib phrase matcher |
| `src/hey_claude/transcribe.py` | MLX Whisper wrapper |
| `src/hey_claude/launcher.py` | turning a command into a `claude` invocation |
| `src/hey_claude/listener.py` | the loop that ties the stages together |
| `src/hey_claude/{doctor,service,appbundle,train}.py` | ops + setup commands |
| `src/hey_claude/cli.py` | argparse front-end |
| `docs/ARCHITECTURE.md` | how and why it's built this way |

## Guidelines

- **Keep heavy imports lazy.** `doctor`/`config`/`train` must work even when
  audio/ML deps are missing — import `sounddevice`, `mlx_whisper`, `openwakeword`
  *inside* the function that needs them.
- **Never pass a spoken command through a shell.** It's always a single argv
  element. There's a test that enforces this; don't regress it.
- **Add a test** for new matching/parsing logic. The pure pieces (`match_wake`,
  config coercion, `render_template`) are easy to unit-test without a mic.
- Run `pytest` before opening a PR. CI runs it on macOS for Python 3.11–3.13.

## Ideas / good first issues

- A menu-bar UI (rumps) showing listen state and recent dispatches.
- An optional speaker-verification stage (openWakeWord's verifier model) so it
  prefers your voice.
- A `--once` mode for scripting / testing without the daemon.
- Ship a community-trained `hey_claude.onnx` so first run needs no Colab.
