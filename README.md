# hey-claude

[![CI](https://github.com/tachyurgy/hey-claude/actions/workflows/ci.yml/badge.svg)](https://github.com/tachyurgy/hey-claude/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python 3.10–3.13](https://img.shields.io/badge/python-3.10–3.13-blue.svg)
![Platform: macOS (Apple Silicon)](https://img.shields.io/badge/platform-macOS%20·%20Apple%20Silicon-lightgrey.svg)

> Say **"Hey Claude, fix the failing tests"** out loud. A Claude Code agent
> spins up in the background and gets to work. Fully on-device — no cloud wake
> word, no API key to listen, no per-user signup.

`hey-claude` is an always-listening wake word for [Claude Code](https://code.claude.com)
on macOS. When it hears **"hey claude,"** it captures what you say next,
transcribes it locally, and dispatches it as a background agent with
`claude --bg`. You keep talking; the agents keep stacking up in `claude agents`.

```
┌─────────┐   ┌───────────────┐   ┌──────────────┐   ┌──────────────────┐   ┌───────────────────┐
│   mic   │──▶│  openWakeWord │──▶│  endpoint by │──▶│   MLX Whisper    │──▶│ claude --bg       │
│ 16kHz   │   │ "hey claude"? │   │   silence    │   │ (transcribe cmd) │   │ "<your command>"  │
└─────────┘   └───────────────┘   └──────────────┘   └──────────────────┘   └───────────────────┘
   always-on    tiny on-device       VAD on the         Apple-Silicon GPU       detached agent,
   capture      classifier           command tail        local transcription    survives terminal
```

Everything before the final step stays on your machine. The only thing that
leaves is the command you ask your agent to run — and that goes exactly where
that agent already sends it.

> **The story behind it:** [I taught my Mac to launch coding agents when I say
> "Hey Claude"](https://consulting.levelbrook.com/writing/hey-claude-on-device-wake-word/)
> — the on-device pipeline, and how the wake words were trained on free cloud GPUs.

---

## Work with us

`hey-claude` is built and maintained by **[Levelbrook Consulting](https://consulting.levelbrook.com)**,
a senior software engineering practice. The same care that went into the
on-device audio pipeline, the safe single-argv dispatch, and the
trained-from-scratch wake words is the care we bring to client work: Ruby/Rails,
Python, AWS, and AI tooling that has to survive production.

**We take on contract work — corp-to-corp, remote, Pacific Time.** If you're
building agent-driven tooling, voice/ML features, or just need senior hands on a
Rails or Python system, [get in touch →](mailto:levelbrookteam@gmail.com?subject=Engineering%20consulting%20inquiry)
or read [how we work](https://consulting.levelbrook.com).

---

## Install

Requires **macOS on Apple Silicon**, **Python 3.10–3.13**, and **[Claude Code](https://code.claude.com)** `≥ 2.1.139` (for `claude --bg`).

```bash
# Homebrew (recommended) — installs PortAudio + a Python env for you
brew install tachyurgy/tap/hey-claude

# or pipx (isolated)
brew install portaudio
pipx install hey-claude

# or pip into a 3.12 venv
brew install portaudio
pip install hey-claude
```

Then run the first-run check, which tells you exactly what (if anything) is missing:

```bash
hey-claude doctor
```

## Quickstart

It works the moment it's installed — a **"hey claude" wake word ships in the
box**, so there's no training step to start:

```bash
hey-claude          # starts listening with the bundled "hey claude" model
```

Now say: **"Hey Claude, add type hints to utils.py and run the tests."**
You'll hear a chime, then a confirmation, and a new row appears in `claude agents`.

Want a different trigger phrase? Several wake words ship bundled — switch with one
command (see [Bundled wake words](#bundled-wake-words-mileage-may-vary)):

```bash
hey-claude models             # list the bundled + installed models
hey-claude models use hey_computer
```

## Microphone permission (the one macOS gotcha)

macOS grants microphone access to an app with a *stable identity*. There are two paths:

- **Running from Terminal:** the first time you start `hey-claude`, macOS prompts
  for mic access for your terminal — click **Allow**. Done.
- **Running at login / headless:** a bare CLI launched by `launchd` often can't
  raise that prompt. Build the bundled `.app`, which has its own identity macOS
  can grant:

  ```bash
  hey-claude app                 # builds ~/Applications/Hey Claude.app
  open "$HOME/Applications/Hey Claude.app"   # click Allow on the mic prompt
  ```

  Then add it to **System Settings → General → Login Items** to start at login.

## Bundled wake words (mileage may vary)

Several openWakeWord models ship in the box, so you can pick a trigger phrase
without training anything:

| Model | Say | Notes |
|---|---|---|
| `hey_claude` *(default)* | "hey claude" | the phrase the tool is named for |
| `okay_claude` | "okay claude" | alternate Claude trigger |
| `hey_computer` | "hey computer" | Star-Trek style, distinct from any product name |
| `hey_assistant` | "hey assistant" | generic, agent-neutral |
| `hey_agent` | "hey agent" | generic, agent-neutral |

```bash
hey-claude models                 # list bundled + installed, shows the active one
hey-claude models use hey_computer
```

**Mileage may vary.** These are small models trained on a modest synthetic-speech
budget — they're speaker-independent, but real-world accuracy and the
false-positive rate depend on your mic, room, and accent. If one fires too often,
raise `threshold`; if it misses you, lower it. If none are reliable enough, train
your own dialed-in model (next section).

### Training your own wake word

openWakeWord models are trained on **100% synthetic speech** — you never record
your voice, and the result is speaker-independent. The fastest free path is the
official Colab notebook:

```bash
hey-claude train        # opens the notebook + prints the steps
```

Set the phrase, pick a free T4 GPU, *Run all* (~10 min), download the `.onnx`,
then `hey-claude import-model <path>`. See
[openWakeWord](https://github.com/dscripka/openWakeWord) for details. There's a
headless, scriptable version of the same recipe in
[`training/train_wakewords.py`](training/train_wakewords.py).

**No model at all?** The fallback engine matches the phrase from a Whisper
transcript with zero setup (slightly more CPU):

```bash
hey-claude config set engine whisper
```

## Configuration

Everything is configurable two ways — the CLI, or by editing the config file
directly. Config lives at `~/.config/hey-claude/config.toml`
(`hey-claude config path`):

```bash
hey-claude config show                       # print every setting
hey-claude config set threshold 0.6          # change one from the CLI
hey-claude config edit                       # open the TOML in $EDITOR
```

The file is plain TOML — `hey-claude config edit` just opens it; any key in the
table below can be set there by hand and takes effect on next start.

## Launch any agent — not just Claude

A wake doesn't *have* to run `claude`. It runs whatever agent you point it at.
Switch with one command:

```bash
hey-claude agent list                # see the presets + which is active
hey-claude agent use codex           # now "hey claude, <task>" drives Codex
```

| Preset | What a heard command runs |
|---|---|
| `claude-bg` *(default)* | `claude --bg "<command>"` — detached background agent, watch it in `claude agents` |
| `claude-terminal` | a new Terminal running `claude "<command>"` so you can supervise/approve |
| `claude-print` | `claude -p "<command>"` headless one-shot, output appended to the log |
| `codex` | `codex exec "<command>"` — OpenAI Codex CLI |
| `aider` | `aider --yes --message "<command>"` |
| `opencode` | `opencode run "<command>"` |
| `gemini` | `gemini --prompt "<command>"` |

The external presets are honest starting points — third-party CLIs change their
flags, so confirm yours and tune the template.

### Fully custom — any command at all

Under the hood every preset just sets `launch_template`, which you can write
yourself. It's a shell-style token list; placeholders are substituted **per
token**, and the `{command}` token is always passed as a *single* argument, so a
spoken command can never inject extra flags or shell metacharacters:

```bash
hey-claude config set launch_template 'my-agent --name {name} --prompt {command}'
```

Or in the file directly:

```toml
# ~/.config/hey-claude/config.toml
launch_template = 'claude --bg --name {name} --permission-mode acceptEdits --model opus {command}'
```

Placeholders: `{command}` `{name}` `{permission_mode}` `{model}` `{claude_bin}`.
Leave `launch_template` empty to use the native `claude` launch modes (which keep
full support for `permission_mode`, `claude_model`, and `max_concurrent`).

### Configurable sounds

Each event plays a sound; override any of them with a file path *or* a macOS
system-sound name (from `/System/Library/Sounds`), or `none` to silence one:

```bash
hey-claude config set sound_wake Hero            # system sound by name
hey-claude config set sound_dispatch ~/snd/go.wav
hey-claude config set sound_cancel none
hey-claude config set chime false                # disable all sounds
```

| Event | Default | When it plays |
|---|---|---|
| `sound_wake` | Tink | the wake word was detected — start talking |
| `sound_dispatch` | Glass | an agent was successfully dispatched |
| `sound_cancel` | Funk | wake fired but no command followed / you cancelled |
| `sound_error` | Basso | dispatch failed |

### Key settings

| Key | Default | Notes |
|---|---|---|
| `engine` | `openwakeword` | or `whisper` (no model file needed) |
| `wakeword_model` | `""` | bundled name (`hey_claude`…), a path, or empty for the default |
| `wake_phrase` | `hey claude` | also used by the whisper engine |
| `threshold` | `0.5` | openWakeWord score; higher = fewer false positives |
| `whisper_model` | `mlx-community/whisper-large-v3-turbo` | command transcription |
| `launch_template` | `""` | run any agent; empty = native `claude` modes (see above) |
| `permission_mode` | `""` | e.g. `acceptEdits`, `plan` for dispatched agents |
| `claude_model` | `""` | model for dispatched agents |
| `max_concurrent` | `0` | 0 = unlimited; else refuse to dispatch past N live bg sessions |
| `confirm` | `false` | require Enter before each dispatch |

## Run at login (launchd)

```bash
hey-claude install     # installs a launchd user agent (starts at login, restarts on crash)
hey-claude status
hey-claude stop / start / uninstall
```

Grant mic permission first (see above) or the service will receive silent audio.

## Uninstalling

`hey-claude` keeps state in three places a package manager won't clean up: the
launchd agent (`~/Library/LaunchAgents`), your config and trained wake-word
models (`~/.config/hey-claude`), and the `.app` bundle (`~/Applications`). The
teardown command removes all three:

```bash
hey-claude uninstall          # just the launchd agent
hey-claude uninstall --all    # + config, trained models, and the .app (asks first)
```

Run `--all` **before** removing the package, since `brew`/`pipx`/`pip` can't
reach those paths. Two things it can't do for you: clear the macOS microphone
grant (revoke it in **System Settings → Privacy & Security → Microphone**), and
remove the package itself:

```bash
brew uninstall hey-claude   #  or:  pipx uninstall hey-claude  /  pip uninstall hey-claude
```

## Safety

A voice trigger carries false-positive risk, so the defaults are conservative:
the `bg` launch mode runs each agent in Claude Code's supervisor (with its normal
permission prompts and per-session git worktree isolation). If you set a
non-interactive permission mode like `acceptEdits` or `bypassPermissions`, an
agent can act without you watching — scope it deliberately, and consider
`max_concurrent` and `confirm`.

## How it works

1. **Wake** — openWakeWord runs a ~250 KB classifier over a frozen Google speech
   embedding on each 80 ms frame. A score above `threshold` (outside a short
   refractory window) is a wake. Lowest possible CPU for always-on listening.
2. **Endpoint** — once woken, a small energy VAD records the command and stops
   after ~800 ms of trailing silence, keeping a short pre-roll so the first
   syllable isn't clipped.
3. **Transcribe** — the command audio goes to MLX Whisper (Metal GPU), which
   returns text in well under a second on Apple Silicon.
4. **Dispatch** — the text is passed verbatim as a single argument to
   `claude --bg`, which hands it to Claude Code's background-session supervisor.

## Documentation

- [The build log](https://consulting.levelbrook.com/writing/hey-claude-on-device-wake-word/) — how it works and how the wake words were trained (Levelbrook engineering blog)
- [Architecture](docs/ARCHITECTURE.md) — the four-stage pipeline and why it's built this way
- [Contributing](CONTRIBUTING.md) — setup, project layout, good first issues
- [Changelog](CHANGELOG.md)
- [Release runbook](RELEASE.md) — tagging, Homebrew, PyPI

## Development

```bash
git clone https://github.com/tachyurgy/hey-claude
cd hey-claude
brew install portaudio
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## License

MIT. See [LICENSE](LICENSE).

---

Built and maintained by **[Levelbrook Consulting](https://consulting.levelbrook.com)** —
a senior software engineering practice (Rails · Python · AWS · AI tooling).
Available for contract work, corp-to-corp.
[Get in touch →](mailto:levelbrookteam@gmail.com?subject=Engineering%20consulting%20inquiry)
