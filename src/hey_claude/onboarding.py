"""The "make it yours" cheat-sheet — the three knobs people actually retune.

Customizability is core behavior, not a footnote, so the same compact block is
printed in the first-run doctor, right after `install`, and from the sounds/agent
help. One source of truth keeps the wording (and the exact commands) consistent
everywhere they appear.
"""

from __future__ import annotations

from . import agents, sounds
from .config import Config


def tips(cfg: Config) -> str:
    """A short, copy-pasteable block showing each knob's current value + how to
    change it, tailored to the live config."""
    phrase = cfg.wake_phrase or "hey claude"
    pack = cfg.soundpack or "warm"
    agent = agents.describe_active(cfg.launch_template, cfg.launch_mode)
    n_packs = len(sounds.BUILTIN_PACKS)
    packs_dir = sounds.user_packs_dir()
    lines = [
        "Make it yours — the three knobs people retune most:",
        "",
        f'  Wake phrase   now: "{phrase}"',
        '      change:  hey-claude wake "<phrase>"',
        "",
        f"  Soundpack     now: {pack}    ({n_packs} built in — clicks, voices, more)",
        f"      browse:  hey-claude sounds packs      switch:  hey-claude sounds pack <name>",
        f"      yours:   drop a folder of wake/endpoint/dispatch/cancel/error sounds in",
        f"               {packs_dir}/<name>/   then  hey-claude sounds pack <name>",
        "",
        f"  Agent command now: {agent}",
        "      change:  hey-claude agent use <preset>   (claude-bg, codex, aider, gemini …)",
        "      custom:  hey-claude agent set '<your CLI with {command}>'",
    ]
    return "\n".join(lines)


def print_tips(cfg: Config) -> None:
    print(tips(cfg))
