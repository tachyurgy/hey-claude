# Show HN draft

A starting point for the launch post — tighten before you submit.

---

**Title:** Show HN: Hey Claude – an on-device voice wake word that dispatches Claude Code agents

**URL:** https://github.com/tachyurgy/hey-claude

**Body:**

I wanted to say "Hey Claude, fix the failing tests" out loud and have a coding
agent actually start working — without piping my mic to a cloud service all day.

hey-claude is a macOS tool that listens for "hey claude," transcribes whatever
you say next, and dispatches it as a Claude Code background agent
(`claude --bg`). You keep talking; the agents stack up in `claude agents`.

The whole thing is local until the very last step:

- **openWakeWord** (a ~250 KB classifier on a frozen speech-embedding backbone)
  does the always-on listening at ~0.1% CPU. It's trained on synthetic speech, so
  there's no recording step and it's speaker-independent.
- A small energy VAD endpoints the command (with pre-roll so it doesn't clip your
  first word).
- **MLX Whisper** transcribes on the Apple-Silicon GPU in under a second.
- Only then does anything leave the machine, via `claude --bg`.

Design notes I found interesting:

- The progressive-gating shape (tiny model → VAD → GPU model → network) is what
  makes always-on listening cheap enough to leave running.
- The macOS microphone-permission story is the real work: TCC grants access to a
  *stable identity*, so a bare CLI or launchd process often can't even raise the
  prompt. The tool generates a tiny ad-hoc-signed `.app` to get a real identity.
- A spoken command is always passed as a single argv element — never through a
  shell — so "ship it; rm -rf /" can't become a shell injection.

No API key to listen, no per-user signup, MIT-licensed. There's also a
no-model-needed fallback engine that just uses Whisper for the wake word too.

Feedback welcome — especially on the wake-word false-positive/latency trade-off
and the permission UX.
