# hey-claude

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
leaves is the command you ask Claude Code to run — and that goes exactly where
Claude Code already sends it.

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

```bash
# 1. Get a free "hey claude" wake-word model (no microphone, ~10 min, trains in your browser)
hey-claude train
hey-claude import-model ~/Downloads/hey_claude.onnx

# 2. Start listening
hey-claude
```

Now say: **"Hey Claude, add type hints to utils.py and run the tests."**
You'll hear a chime, then a confirmation, and a new row appears in `claude agents`.

**Don't want to train anything?** The fallback engine needs no model and works immediately:

```bash
hey-claude config set engine whisper
hey-claude
```

It transcribes each utterance with Whisper and matches the phrase directly —
zero setup, slightly more CPU than the dedicated wake model.

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

## Training your wake word

openWakeWord models are trained on **100% synthetic speech** — you never record
your voice, and the result is speaker-independent (it responds to anyone). The
fastest free path is the official Colab notebook:

```bash
hey-claude train        # opens the notebook + prints the steps
```

Set the phrase to `hey claude`, pick a free T4 GPU, *Run all* (~10 min), download
`hey_claude.onnx`, then `hey-claude import-model <path>`. See
[openWakeWord](https://github.com/dscripka/openWakeWord) for details.

## Configuration

Config lives at `~/.config/hey-claude/config.toml` (`hey-claude config path`).
Inspect and change it with the CLI or edit the file directly:

```bash
hey-claude config show
hey-claude config set launch_mode terminal
hey-claude config edit
```

### Launch modes — how a heard command becomes an agent

| `launch_mode` | What happens |
|---|---|
| `bg` *(default)* | `claude --bg "<command>"` — detached background agent, watch it in `claude agents` |
| `terminal` | opens a new Terminal running `claude "<command>"` so you can supervise/approve |
| `print` | `claude -p "<command>"` headless one-shot, output appended to the log |

### Configurable invoke command

Override the invocation entirely with `launch_template` (in the config). It's a
shell-style token list; placeholders are substituted **per token**, and the
`{command}` token is always passed as a *single* argument, so a spoken command
can never inject extra flags or shell metacharacters:

```toml
# ~/.config/hey-claude/config.toml
launch_template = 'claude --bg --name {name} --permission-mode acceptEdits --model opus {command}'
```

Placeholders: `{command}` `{name}` `{permission_mode}` `{model}` `{claude_bin}`.

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
| `wake_phrase` | `hey claude` | also used by the whisper engine |
| `threshold` | `0.5` | openWakeWord score; higher = fewer false positives |
| `whisper_model` | `mlx-community/whisper-large-v3-turbo` | command transcription |
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

## Development

```bash
git clone https://github.com/tachyurgy/hey-claude
cd hey-claude
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## License

MIT. See [LICENSE](LICENSE).
