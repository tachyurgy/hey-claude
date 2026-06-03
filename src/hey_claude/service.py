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


def _remove_path(path: Path) -> None:
    """Delete a file, symlink, or directory tree at ``path`` (no-op if absent)."""
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _residuals_note() -> None:
    print("\nTwo things this can't do for you:")
    print("  • Revoke microphone access — System Settings → Privacy & Security →")
    print('    Microphone, and remove "Hey Claude" (or your terminal). macOS owns that grant.')
    print("  • Remove the package itself — run whichever you installed with:")
    print("      brew uninstall hey-claude   ·   pipx uninstall hey-claude   ·   pip uninstall hey-claude")


def purge(*, assume_yes: bool = False) -> int:
    """Full teardown: launchd agent + config/models + the bundled ``.app``.

    Deliberately does NOT uninstall the package (that's brew/pipx/pip's job) and
    cannot clear the macOS microphone grant (TCC is OS-owned). Both are printed
    as follow-ups. The config dir holds the user's *trained* wake-word models, so
    we confirm before deleting unless ``assume_yes``.
    """
    from . import appbundle
    from .config import config_home

    targets = [
        ("launchd agent", plist_path()),
        ("config + models", config_home()),
        (".app bundle", appbundle.default_dest()),
    ]
    present = [(label, p) for label, p in targets if p.exists()]

    if not present:
        print("· nothing to remove — no launchd agent, config dir, or .app bundle found.")
        _residuals_note()
        return 0

    print("This will permanently delete:")
    for label, p in present:
        print(f"  • {label:<17} {p}")
    if any(label == "config + models" for label, _ in present):
        print("\n  Your trained wake-word models live in the config dir — they will be lost.")

    if not assume_yes:
        try:
            reply = input("\nProceed? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            reply = ""
        if reply not in ("y", "yes"):
            print("· aborted; nothing removed.")
            return 1

    # Unload the agent before deleting its plist so launchd doesn't keep a stale
    # job pointing at a path we're about to remove.
    if plist_path().exists():
        _launchctl("unload", "-w", str(plist_path()))

    failures = 0
    for label, p in present:
        try:
            _remove_path(p)
            print(f"✓ removed {label}: {p}")
        except OSError as exc:
            failures += 1
            print(f"✗ could not remove {p}: {exc}", file=sys.stderr)

    _residuals_note()
    return 1 if failures else 0


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
