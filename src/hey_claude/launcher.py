"""Turn a transcribed command into a running Claude Code agent.

Three launch modes (config ``launch_mode``):

* ``bg``       — ``claude --bg "<command>"``: a detached background agent managed
  by Claude Code's supervisor. Survives terminal closure; watch it with
  ``claude agents``. This is the default and the design the tool was built around.
* ``terminal`` — open a new Terminal window running ``claude "<command>"`` so you
  can watch and approve tool calls interactively.
* ``print``    — ``claude -p "<command>"``: a headless one-shot, output appended
  to the log file. No supervision; use deliberately.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import Config, log_path


class LaunchError(RuntimeError):
    pass


@dataclass
class LaunchResult:
    mode: str
    detail: str  # session id, log path, or a human-readable note


def resolve_claude_bin(cfg: Config) -> str:
    candidate = cfg.claude_bin or "claude"
    found = shutil.which(candidate)
    if found:
        return found
    # launchd/app contexts have no PATH; probe the usual install locations.
    for guess in (
        Path(candidate).expanduser(),
        Path.home() / ".local/bin/claude",
        Path("/opt/homebrew/bin/claude"),
        Path("/usr/local/bin/claude"),
    ):
        if guess.is_file() and os.access(guess, os.X_OK):
            return str(guess)
    raise LaunchError(
        "Could not find the `claude` executable. Install Claude Code, or set its "
        "full path with:  hey-claude config set claude_bin /full/path/to/claude"
    )


def count_bg_sessions(claude_bin: str) -> int:
    """Number of live background sessions, via ``claude agents --json`` (0 on error)."""
    try:
        proc = subprocess.run(
            [claude_bin, "agents", "--json"],
            capture_output=True, text=True, timeout=15,
        )
        data = json.loads(proc.stdout or "[]")
        return len(data) if isinstance(data, list) else 0
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0


def session_name(cfg: Config, command: str) -> str:
    words = re.findall(r"[\w']+", command)[:6]
    slug = " ".join(words) if words else "voice task"
    return f"{cfg.name_prefix}: {slug}"[:60]


def launch(cfg: Config, command: str) -> LaunchResult:
    command = command.strip()
    if not command:
        raise LaunchError("Empty command — nothing to dispatch.")

    # A custom launch_template can target ANY agent CLI, so only require the
    # `claude` binary when the template actually references it (or for the
    # built-in claude launch modes below).
    if cfg.launch_template.strip():
        needs_claude = "{claude_bin}" in cfg.launch_template
        claude_bin = resolve_claude_bin(cfg) if needs_claude else (cfg.claude_bin or "claude")
        return _launch_template(cfg, claude_bin, command)

    claude_bin = resolve_claude_bin(cfg)
    if cfg.max_concurrent and cfg.launch_mode == "bg":
        live = count_bg_sessions(claude_bin)
        if live >= cfg.max_concurrent:
            raise LaunchError(
                f"{live} background sessions already running "
                f"(max_concurrent={cfg.max_concurrent}). Skipping dispatch."
            )

    if cfg.launch_mode == "bg":
        return _launch_bg(cfg, claude_bin, command)
    if cfg.launch_mode == "terminal":
        return _launch_terminal(cfg, claude_bin, command)
    if cfg.launch_mode == "print":
        return _launch_print(cfg, claude_bin, command)
    raise LaunchError(f"Unknown launch_mode: {cfg.launch_mode!r}")


def render_template(cfg: Config, claude_bin: str, command: str) -> list[str]:
    """Expand ``cfg.launch_template`` into an argv list (for testing + execution).

    Tokens are shell-split once; each token then has placeholders substituted.
    The ``{command}`` token is replaced wholesale with the command string as a
    single argv element, so a spoken command can never inject extra arguments.
    """
    import shlex

    subs = {
        "command": command,
        "name": session_name(cfg, command),
        "permission_mode": cfg.permission_mode,
        "model": cfg.claude_model,
        "claude_bin": claude_bin,
    }
    argv: list[str] = []
    for tok in shlex.split(cfg.launch_template):
        if tok == "{command}":
            argv.append(command)
            continue
        try:
            argv.append(tok.format(**subs))
        except (KeyError, IndexError) as exc:
            raise LaunchError(f"Bad placeholder in launch_template token {tok!r}: {exc}") from exc
    if not argv:
        raise LaunchError("launch_template is empty after expansion.")
    return argv


def _launch_template(cfg: Config, claude_bin: str, command: str) -> LaunchResult:
    argv = render_template(cfg, claude_bin, command)
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise LaunchError(f"Custom launch_template failed: {exc}") from exc
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    m = _BACKGROUNDED.search(out)
    if m:
        return LaunchResult("bg", m.group(1))
    if proc.returncode != 0:
        raise LaunchError(f"launch_template exited {proc.returncode}: {out[:400]}")
    return LaunchResult("template", out.splitlines()[0] if out else "ran custom command")


def _common_session_flags(cfg: Config) -> list[str]:
    flags: list[str] = []
    if cfg.permission_mode:
        flags += ["--permission-mode", cfg.permission_mode]
    if cfg.claude_model:
        flags += ["--model", cfg.claude_model]
    return flags


_BACKGROUNDED = re.compile(r"backgrounded\s*[·.\-]\s*([0-9a-f]{6,})", re.IGNORECASE)


def _launch_bg(cfg: Config, claude_bin: str, command: str) -> LaunchResult:
    args = [claude_bin, "--bg", "--name", session_name(cfg, command)]
    args += _common_session_flags(cfg)
    args.append(command)
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        raise LaunchError(f"Failed to dispatch background agent: {exc}") from exc
    out = (proc.stdout or "") + (proc.stderr or "")
    m = _BACKGROUNDED.search(out)
    if m:
        return LaunchResult("bg", m.group(1))
    if proc.returncode != 0:
        raise LaunchError(f"claude --bg exited {proc.returncode}: {out.strip()[:400]}")
    return LaunchResult("bg", out.strip().splitlines()[0] if out.strip() else "dispatched")


def _launch_terminal(cfg: Config, claude_bin: str, command: str) -> LaunchResult:
    # Build the shell line that runs inside the new Terminal tab, then embed it
    # in an AppleScript string (escaping backslashes and double quotes once).
    shell_line = f"{_shq(claude_bin)} {_shq(command)}"
    script = f'tell application "Terminal" to do script "{_osa(shell_line)}"'
    script += '\ntell application "Terminal" to activate'
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError) as exc:
        raise LaunchError(f"Failed to open Terminal: {exc}") from exc
    return LaunchResult("terminal", "opened a new Terminal session")


def _launch_print(cfg: Config, claude_bin: str, command: str) -> LaunchResult:
    args = [claude_bin, "-p", command, "--output-format", "json"]
    args += _common_session_flags(cfg)
    lp = log_path()
    lp.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lp, "ab")
    fh.write(f"\n=== {command!r} ===\n".encode())
    fh.flush()
    try:
        subprocess.Popen(args, stdout=fh, stderr=fh, start_new_session=True)
    except (OSError, subprocess.SubprocessError) as exc:
        fh.close()
        raise LaunchError(f"Failed to start headless agent: {exc}") from exc
    return LaunchResult("print", str(lp))


def _shq(s: str) -> str:
    """POSIX shell single-quote escaping."""
    return "'" + s.replace("'", "'\\''") + "'"


def _osa(s: str) -> str:
    """Escape a string for embedding inside an AppleScript double-quoted literal."""
    return s.replace("\\", "\\\\").replace('"', '\\"')
