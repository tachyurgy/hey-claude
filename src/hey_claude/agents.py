"""Agent presets — point hey-claude at *any* agent CLI, not just Claude Code.

A wake fires, your speech is transcribed, and the result is handed to whatever
command an agent preset defines. The spoken text is always substituted into the
``{command}`` placeholder as a **single argv element** (never re-split, never
through a shell), so a misheard or adversarial command can't inject extra flags.

Two kinds of preset:

* The **claude** built-ins (``claude-bg`` / ``claude-terminal`` / ``claude-print``)
  clear ``launch_template`` and use the native launch modes, keeping full support
  for ``permission_mode`` / ``claude_model`` / ``max_concurrent``.
* The **external** presets set ``launch_template`` to another agent's CLI. These
  are honest starting points — third-party flags drift, so confirm yours and edit
  the template (``hey-claude config set launch_template '…'``) to taste.

Placeholders available in any template: ``{command}`` ``{name}``
``{permission_mode}`` ``{model}`` ``{claude_bin}``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    key: str
    summary: str
    launch_mode: str  # used when template == "" (the claude built-ins)
    template: str     # launch_template to set; "" => use the built-in launch_mode


# Ordered: claude built-ins first, then external examples.
PRESETS: dict[str, Preset] = {
    "claude-bg": Preset(
        "claude-bg",
        "Claude Code detached background agent (default) — watch it in `claude agents`.",
        "bg", "",
    ),
    "claude-terminal": Preset(
        "claude-terminal",
        "Claude Code in a new Terminal window so you can supervise and approve.",
        "terminal", "",
    ),
    "claude-print": Preset(
        "claude-print",
        "Claude Code headless one-shot (`claude -p`), output appended to the log.",
        "print", "",
    ),
    "codex": Preset(
        "codex",
        "OpenAI Codex CLI, non-interactive (example — verify your `codex` flags).",
        "bg", "codex exec {command}",
    ),
    "aider": Preset(
        "aider",
        "Aider, one message per dispatch (example — verify your `aider` flags).",
        "bg", "aider --yes --message {command}",
    ),
    "opencode": Preset(
        "opencode",
        "opencode run (example — verify your `opencode` flags).",
        "bg", "opencode run {command}",
    ),
    "gemini": Preset(
        "gemini",
        "Gemini CLI one-shot (example — verify your `gemini` flags).",
        "bg", "gemini --prompt {command}",
    ),
}

DEFAULT = "claude-bg"


def get(key: str) -> Preset | None:
    return PRESETS.get(key)


# Placeholders a launch_template may use (substituted per-token, never re-split).
PLACEHOLDERS = ("{command}", "{name}", "{permission_mode}", "{model}", "{claude_bin}")


def validate_template(template: str) -> str | None:
    """Return an error string if ``template`` can't dispatch a command, else None.

    The only hard requirement is a ``{command}`` placeholder — without it the
    spoken task would never reach the agent. We also reject the obvious foot-gun
    of an empty command word.
    """
    t = (template or "").strip()
    if not t:
        return "empty template — give a command, e.g. 'codex exec {command}'"
    if "{command}" not in t:
        return "template must contain the {command} placeholder (where the spoken task goes)"
    return None


def describe_active(launch_template: str, launch_mode: str) -> str:
    """Best-effort label for the currently-configured agent."""
    tmpl = (launch_template or "").strip()
    if tmpl:
        for p in PRESETS.values():
            if p.template and p.template == tmpl:
                return p.key
        return f"custom · {tmpl}"
    for p in PRESETS.values():
        if not p.template and p.launch_mode == launch_mode:
            return p.key
    return f"claude ({launch_mode})"
