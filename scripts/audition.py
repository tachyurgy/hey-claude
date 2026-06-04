#!/usr/bin/env python3
"""Soundpack audition viewer — listen through every pack and pick your favorites.

    python scripts/audition.py            # interactive
    python scripts/audition.py 9          # play pack 9 and drop into the prompt
    python scripts/audition.py tour       # play every pack's wake cue, then the prompt

It scans *every* folder under src/hey_claude/soundpacks/ (plus the studio default
and any custom packs in your config dir), numbers them, and plays cues on demand.
Built for fast browsing — type a number to hear a whole pack, an event name to
hear just that cue, `jump N` to move without playing, `set N` to make one active.

Commands (also: `help`):
    list                 numbered list of all packs
    9        / play 9    play pack 9 (wake → endpoint → dispatch → cancel → error)
    jump 9   / goto 9    select pack 9 without playing
    play                 replay the current pack
    9 dispatch           play just the dispatch cue of pack 9
    wake | endpoint | dispatch | cancel | error   (or w/e/d/c/r) — cue of current pack
    all                  every cue of the current pack
    tour [event]         play one cue (default wake) for EVERY pack — hear them all
    next / n , prev / p  step through packs (and play)
    info / i [9]         show the files in a pack
    set [9]              save a pack as your active soundpack (config.toml)
    quit / q
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

# Make the package importable when run straight from the repo (no install needed).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from hey_claude import sounds  # noqa: E402
from hey_claude.config import Config  # noqa: E402

EVENTS = sounds.EVENTS  # wake, endpoint, dispatch, cancel, error
EVENT_ALIASES = {"w": "wake", "e": "endpoint", "d": "dispatch", "c": "cancel", "r": "error"}

# Friendly descriptions, pulled from whatever registries are available.
try:
    from importlib import import_module
    _sfx = import_module("scripts.build_sfx_packs") if False else None
except Exception:  # pragma: no cover
    _sfx = None


def _descriptions() -> dict[str, str]:
    desc = dict(sounds.BUILTIN_PACKS)  # studio + synth packs
    # CC0 pack descriptions live in the build script; import best-effort.
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import build_sfx_packs  # type: ignore
        for name, (d, _m) in build_sfx_packs.PACKS.items():
            desc.setdefault(name, d)
    except Exception:
        pass
    return desc


def discover() -> list[str]:
    """All pack names: studio first, then bundled folders, then custom packs."""
    names = ["studio"]
    bundled = sorted(p.name for p in sounds._PACKS_DIR.iterdir() if p.is_dir())
    names += [b for b in bundled if b not in names]
    user_root = sounds.user_packs_dir()
    if user_root.is_dir():
        for child in sorted(user_root.iterdir()):
            if child.is_dir() and child.name not in names:
                names.append(child.name)
    return names


class Audition:
    def __init__(self, packs: list[str]):
        self.packs = packs
        self.desc = _descriptions()
        self.cur = 0

    # -- playback ----------------------------------------------------------
    def _play(self, path: Path | None, label: str) -> None:
        if path is None or not path.exists():
            print(f"    · {label}: (none)")
            return
        print(f"    ♪ {label:<9} {path.name}")
        subprocess.run(["afplay", str(path)])

    def play_event(self, idx: int, event: str) -> None:
        pack = self.packs[idx]
        self._play(sounds.event_sound(event, "", pack), event)

    def play_pack(self, idx: int) -> None:
        pack = self.packs[idx]
        print(f"\n▶  [{idx + 1}] {pack}  —  {self.desc.get(pack, '')}")
        for ev in EVENTS:
            self.play_event(idx, ev)
            time.sleep(0.15)

    def tour(self, event: str = "wake") -> None:
        """Play one cue (default: wake) for *every* pack, back to back — the fast
        way to hear all the voices."""
        print(f"\n♫ touring all {len(self.packs)} packs — playing each one's '{event}' cue")
        print("  (Ctrl-C to stop the tour)\n")
        try:
            for i, pack in enumerate(self.packs):
                print(f"  [{i + 1:>2}] {pack:<11} {self.desc.get(pack, '')}")
                self._play(sounds.event_sound(event, "", pack), event)
                time.sleep(0.2)
        except KeyboardInterrupt:
            print("\n  · tour stopped.")

    # -- views -------------------------------------------------------------
    def list_packs(self) -> None:
        print()
        for i, pack in enumerate(self.packs):
            mark = "→" if i == self.cur else " "
            print(f"  {mark} {i + 1:>2}. {pack:<18} {self.desc.get(pack, '')}")
        print(f"\n  current: [{self.cur + 1}] {self.packs[self.cur]}    "
              f"(type a number to play · `help` for commands)")

    def info(self, idx: int) -> None:
        pack = self.packs[idx]
        print(f"\n  [{idx + 1}] {pack}  —  {self.desc.get(pack, '')}")
        for ev in EVENTS:
            files = sounds.pack_event_files(pack, ev)
            if not files:
                # event_sound still resolves it via the studio fallback
                fb = sounds.event_sound(ev, "", pack)
                shown = f"(fallback: {fb.name})" if fb else "(none)"
            else:
                shown = ", ".join(f.name for f in files)
            print(f"    {ev:<9} {shown}")

    def set_active(self, idx: int) -> None:
        pack = self.packs[idx]
        cfg = Config.load()
        cfg.soundpack = pack
        path = cfg.save()
        print(f"  ✓ active soundpack = {pack}   ({path})")

    # -- repl --------------------------------------------------------------
    def _resolve_idx(self, token: str) -> int | None:
        try:
            n = int(token)
        except ValueError:
            return None
        if 1 <= n <= len(self.packs):
            return n - 1
        print(f"  · no pack {n} (have 1–{len(self.packs)})")
        return None

    def handle(self, line: str) -> bool:
        """Return False to quit."""
        parts = line.strip().split()
        if not parts:
            self.play_pack(self.cur)
            return True
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("q", "quit", "exit"):
            return False
        if cmd in ("h", "help", "?"):
            print(__doc__)
            return True
        if cmd in ("list", "ls", "l"):
            self.list_packs()
            return True
        if cmd in ("tour", "voices", "demo"):
            ev = EVENT_ALIASES.get(arg, arg if arg in EVENTS else "wake")
            self.tour(ev)
            return True
        if cmd in ("jump", "goto", "j", "g"):
            idx = self._resolve_idx(arg)
            if idx is not None:
                self.cur = idx
                self.info(idx)
            return True
        if cmd in ("next", "nx"):
            self.cur = (self.cur + 1) % len(self.packs)
            self.play_pack(self.cur)
            return True
        if cmd in ("prev", "pv"):
            self.cur = (self.cur - 1) % len(self.packs)
            self.play_pack(self.cur)
            return True
        if cmd in ("info", "i"):
            idx = self._resolve_idx(arg) if arg else self.cur
            if idx is not None:
                self.info(idx)
            return True
        if cmd == "set":
            idx = self._resolve_idx(arg) if arg else self.cur
            if idx is not None:
                self.set_active(idx)
            return True
        if cmd == "play":
            idx = self._resolve_idx(arg) if arg else self.cur
            if idx is not None:
                self.cur = idx
                self.play_pack(idx)
            return True
        if cmd == "all":
            self.play_pack(self.cur)
            return True
        # single-letter step shortcuts (after `next`/`prev` longhand)
        if cmd == "n":
            self.cur = (self.cur + 1) % len(self.packs)
            self.play_pack(self.cur)
            return True
        if cmd == "p":
            self.cur = (self.cur - 1) % len(self.packs)
            self.play_pack(self.cur)
            return True
        # event of current (or "<n> <event>")
        ev = EVENT_ALIASES.get(cmd, cmd if cmd in EVENTS else "")
        if ev:
            self.play_event(self.cur, ev)
            return True
        # bare number => play that pack; "<n> <event>" => that cue
        idx = self._resolve_idx(cmd)
        if idx is not None:
            self.cur = idx
            ev2 = EVENT_ALIASES.get(arg, arg if arg in EVENTS else "")
            if ev2:
                print(f"\n▶  [{idx + 1}] {self.packs[idx]}")
                self.play_event(idx, ev2)
            else:
                self.play_pack(idx)
            return True
        print(f"  · unknown command: {line!r}   (`help` for the list)")
        return True

    def run(self) -> int:
        print(f"hey-claude soundpack audition — {len(self.packs)} packs")
        self.list_packs()
        while True:
            try:
                line = input("\naudition> ")
            except (EOFError, KeyboardInterrupt):
                print()
                break
            try:
                if not self.handle(line):
                    break
            except Exception as exc:  # never crash the browser on one bad sound
                print(f"  ✗ {exc}")
        print("bye.")
        return 0


def main(argv: list[str]) -> int:
    packs = discover()
    if not packs:
        print("no soundpacks found.")
        return 1
    app = Audition(packs)
    # Optional: `audition.py 9` plays pack 9 immediately; `audition.py tour`
    # plays every pack's wake cue. Either way you land in the prompt afterward.
    if argv:
        if argv[0].lower() in ("tour", "voices", "demo", "all"):
            app.tour(argv[1] if len(argv) > 1 and argv[1] in EVENTS else "wake")
        else:
            idx = app._resolve_idx(argv[0])
            if idx is not None:
                app.cur = idx
                app.play_pack(idx)
    return app.run()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
