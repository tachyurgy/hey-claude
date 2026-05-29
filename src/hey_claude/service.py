"""Run hey-claude as a launchd user agent so it listens at login.

Heads-up on microphone permission: a process launched by launchd often can't
raise the TCC permission prompt and will silently receive empty audio. The
robust fix is the ``.app`` wrapper (``hey-claude app``), which has a stable
identity macOS can grant mic access to. This service is convenient once
permission has already been granted (e.g. by running from Terminal once, or via
the app).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .config import log_path

LABEL = "com.heyclaude.listener"


def plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _program_args() -> list[str]:
    script = shutil.which("hey-claude")
    if script:
        return [script, "run"]
    return [sys.executable, "-m", "hey_claude", "run"]


def _path_env() -> str:
    parts = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"]
    for tool in ("claude", "python3"):
        found = shutil.which(tool)
        if found:
            d = str(Path(found).parent)
            if d not in parts:
                parts.insert(0, d)
    return ":".join(parts)


def render_plist() -> str:
    args = _program_args()
    log = log_path()
    log.parent.mkdir(parents=True, exist_ok=True)
    arg_xml = "\n".join(f"        <string>{a}</string>" for a in args)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LABEL}</string>
    <key>ProgramArguments</key>
    <array>
{arg_xml}
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>{_path_env()}</string>
        <key>HOME</key>
        <string>{Path.home()}</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>ProcessType</key>
    <string>Interactive</string>
    <key>StandardOutPath</key>
    <string>{log}</string>
    <key>StandardErrorPath</key>
    <string>{log}</string>
</dict>
</plist>
"""


def _launchctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True)


def install() -> int:
    path = plist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_plist(), encoding="utf-8")
    _launchctl("unload", str(path))  # idempotent: clear any prior load
    proc = _launchctl("load", "-w", str(path))
    if proc.returncode != 0:
        print(f"✗ launchctl load failed: {proc.stderr.strip()}", file=sys.stderr)
        return 1
    print(f"✓ installed and loaded launchd agent: {path}")
    print(f"  logs: {log_path()}")
    print("  if audio stays silent, grant mic permission via the .app:  hey-claude app")
    return 0


def uninstall() -> int:
    path = plist_path()
    if path.exists():
        _launchctl("unload", "-w", str(path))
        path.unlink()
        print(f"✓ removed launchd agent: {path}")
    else:
        print("· no launchd agent installed.")
    return 0


def start() -> int:
    uid = os.getuid()
    proc = _launchctl("kickstart", "-k", f"gui/{uid}/{LABEL}")
    if proc.returncode != 0:
        # Fall back to load if the agent isn't bootstrapped yet.
        if plist_path().exists():
            _launchctl("load", "-w", str(plist_path()))
            print("✓ started.")
            return 0
        print("✗ not installed — run `hey-claude install` first.", file=sys.stderr)
        return 1
    print("✓ started.")
    return 0


def stop() -> int:
    if plist_path().exists():
        _launchctl("unload", str(plist_path()))
        print("✓ stopped.")
        return 0
    print("· not installed.")
    return 0


def status() -> int:
    proc = _launchctl("list")
    lines = [ln for ln in proc.stdout.splitlines() if LABEL in ln]
    if lines:
        print(f"✓ running:\n  {lines[0].strip()}")
        print(f"  logs: {log_path()}")
        return 0
    print("· not running." + ("" if plist_path().exists() else " (not installed)"))
    return 1
