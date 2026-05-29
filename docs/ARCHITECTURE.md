# Architecture

`hey-claude` is a four-stage pipeline. Each stage is deliberately the *cheapest
thing that works* for its job, so the whole loop can run all day on battery: a
tiny always-on classifier gates an occasional VAD, which gates an occasional
GPU transcription, which gates the only networked step.

```
┌─────────┐   ┌───────────────┐   ┌──────────────┐   ┌──────────────────┐   ┌───────────────────┐
│   mic   │──▶│  openWakeWord │──▶│  endpoint by │──▶│   MLX Whisper    │──▶│ claude --bg       │
│ 16kHz   │   │ "hey claude"? │   │   silence    │   │ (transcribe cmd) │   │ "<your command>"  │
└─────────┘   └───────────────┘   └──────────────┘   └──────────────────┘   └───────────────────┘
  audio.py        wake.py             audio.py            transcribe.py            launcher.py
                                            └──────────── listener.py ───────────┘
```

## Why this shape

The naive design — run Whisper continuously and string-match "hey claude" — burns
the GPU 24/7 and is a privacy liability. Instead we stack progressively heavier
models, each one only invoked when the cheaper stage upstream says "maybe":

| Stage | Cost | Runs | Gates |
|---|---|---|---|
| openWakeWord | ~0.1% CPU/core | every 80 ms frame, always | whether to record at all |
| energy VAD | negligible | only after a wake | how long to record |
| MLX Whisper | ~0.3–0.8 s GPU | once per command | what text to dispatch |
| `claude --bg` | network | once per command | the actual work |

## Stage 1 — Wake detection (`wake.py`, `audio.py`)

A callback-fed `sounddevice` stream (`audio.Microphone`) produces uniform
**1280-sample / 80 ms int16 frames at 16 kHz** — the exact shape openWakeWord
consumes. Frames land in a queue so none are dropped while a later stage is busy.

openWakeWord itself is three sub-models:

1. a **melspectrogram** front-end (audio → frequency features),
2. a **frozen Google speech-embedding** backbone, shared across all wake words,
3. a tiny **classifier head** (the ~250 KB `hey_claude.onnx`) trained on top.

The clever part is (2): because the backbone already "understands speech," the
head can be trained on **100% synthetic** Piper-TTS audio — no recording, and the
result is speaker-independent. `OpenWakeWordEngine.process()` scores each frame
and fires when the score crosses `threshold`, with a `refractory_seconds` window
so one "hey claude" can't trigger twice.

### The whisper fallback engine

If you'd rather not train a model, `engine = whisper` skips stage 1's dedicated
classifier. The listener records each utterance (VAD-gated, so it's *not* a
continuous transcription) and `match_wake()` decides whether it began with the
wake phrase. `match_wake` is pure stdlib: it tokenizes, then fuzzy-matches the
phrase tokens with `difflib`, tolerating "hey, Claude" / "hi claude" / "hey
clyde" and stripping the phrase to return the command remainder in one pass.

## Stage 2 — Endpointing (`audio.record_command`)

Once woken, we need to know when you've *stopped* talking. `record_command` is an
energy VAD with three refinements that matter in practice:

- **Pre-roll** — it keeps the last ~300 ms before speech onset, because people
  start the command the instant the wake word fires; without it you clip the
  first syllable.
- **Onset vs. keep thresholds** — a higher RMS starts capture, a lower one
  sustains it, so a brief mid-sentence pause doesn't end the command.
- **Hard caps** — stops after `silence_ms` of trailing silence, and never records
  past `max_command_seconds` so a stuck mic can't run away.

## Stage 3 — Transcription (`transcribe.py`)

The captured float32 array goes straight to **MLX Whisper** (Apple's MLX
framework, running on the Metal GPU) as an in-memory array — no temp file, no
ffmpeg. The turbo model returns text in well under a second on Apple Silicon.
The model is warmed once at startup so the first real command isn't slow.

The whisper engine re-transcribes a *hit* with the accurate model after the cheap
`whisper-tiny` pass flags it, so the always-listening path stays cheap while the
dispatched command is high-accuracy.

## Stage 4 — Dispatch (`launcher.py`)

The transcript is handed to Claude Code. The default `bg` mode runs
`claude --bg "<command>"`, which Claude Code's per-user supervisor hosts as a
detached background session (survives terminal closure; appears in
`claude agents`). Two other modes exist — `terminal` (a supervised interactive
window) and `print` (headless `claude -p`, logged) — and `launch_template` lets
you specify the invocation entirely.

**Security property:** however the command is launched, the spoken text is passed
as a **single argv element**, never through a shell and never re-split. A command
like `"ship it; rm -rf /"` is one argument to `claude`, not a shell injection.
This is enforced and tested (`tests/test_launcher.py`).

## The loop (`listener.py`)

`Listener` owns one open microphone and funnels both engines into a shared
`_dispatch_command` tail, so command capture, transcript cleanup, the optional
confirm step, audible feedback, and launch are defined exactly once. Audible cues
(`sounds.py`) are non-blocking `afplay` calls — you hear the wake chime before you
start the command, and a distinct dispatch chime when an agent actually launches.

## macOS integration

- **Microphone permission** is the real-world gotcha. macOS TCC grants mic access
  to a *stable identity*; a bare CLI or a `launchd` process often can't even raise
  the prompt. `appbundle.py` generates a minimal, ad-hoc-signed `.app` with an
  `NSMicrophoneUsageDescription` key — a stable identity macOS will prompt for and
  remember.
- **Run at login** via a `launchd` user agent (`service.py`), with an absolute
  `PATH` injected because `launchd` agents inherit none.

## Dependency boundaries

Modules lazy-import their heavy dependencies, so `doctor`, `config`, `train`, and
`models` run (and give useful guidance) even when audio/ML libraries are missing
or broken. `wake.match_wake` references numpy only under `TYPE_CHECKING`, keeping
the matcher pure-stdlib and unit-testable without the full stack.
