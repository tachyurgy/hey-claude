"""Command-line interface for hey-claude."""

from __future__ import annotations

import argparse
import sys
from dataclasses import fields
from pathlib import Path

from . import appbundle, doctor, service, train
from .config import Config, config_path
from .version import __version__


def _apply_run_overrides(cfg: Config, args: argparse.Namespace) -> None:
    if args.engine:
        cfg.engine = args.engine
    if args.launch:
        cfg.launch_mode = args.launch
    if args.threshold is not None:
        cfg.threshold = args.threshold
    if args.whisper_model:
        cfg.whisper_model = args.whisper_model
    if args.device:
        cfg.mic_device = args.device
    if args.permission_mode:
        cfg.permission_mode = args.permission_mode
    if args.claude_model:
        cfg.claude_model = args.claude_model
    if args.no_chime:
        cfg.chime = False
    if args.confirm:
        cfg.confirm = True
    if args.quiet:
        cfg.verbose = False


def cmd_run(args: argparse.Namespace) -> int:
    # Import here so non-listening commands (doctor, config, train) don't pay the
    # cost of audio/ML imports or fail when those deps are absent.
    from .listener import Listener

    cfg = Config.load()
    _apply_run_overrides(cfg, args)
    return Listener(cfg).run()


def cmd_doctor(args: argparse.Namespace) -> int:
    return doctor.run(Config.load())


def cmd_train(args: argparse.Namespace) -> int:
    return train.guide(open_browser=not args.no_open)


def cmd_import_model(args: argparse.Namespace) -> int:
    return train.import_model(args.path, name=args.name or "", activate=not args.no_activate)


def cmd_models(args: argparse.Namespace) -> int:
    if getattr(args, "models_action", None) == "use":
        return train.use_model(args.name)
    return train.list_models()


def cmd_agent(args: argparse.Namespace) -> int:
    from . import agents

    action = getattr(args, "agent_action", None) or "list"
    cfg = Config.load()

    if action == "show":
        print(agents.describe_active(cfg.launch_template, cfg.launch_mode))
        return 0

    if action == "use":
        preset = agents.get(args.name)
        if preset is None:
            print(f"✗ unknown agent preset: {args.name!r}", file=sys.stderr)
            print(f"  choices: {', '.join(agents.PRESETS)}  (or edit launch_template directly)",
                  file=sys.stderr)
            return 1
        cfg.launch_template = preset.template
        cfg.launch_mode = preset.launch_mode
        cfg.save()
        print(f"✓ agent = {preset.key}  —  {preset.summary}")
        if preset.template:
            print(f"  launch_template = {preset.template!r}")
            print("  Tune it any time:  hey-claude config set launch_template '<your command>'")
        else:
            print(f"  launch_mode = {preset.launch_mode!r}  (native Claude Code launch)")
        return 0

    # list (default)
    active = agents.describe_active(cfg.launch_template, cfg.launch_mode)
    print("Agent presets — what a heard command launches:\n")
    for p in agents.PRESETS.values():
        marker = "  ← active" if p.key == active else ""
        print(f"  • {p.key:<16}{marker}")
        print(f"    {p.summary}")
        if p.template:
            print(f"    launch_template: {p.template}")
    print(f"\nActive: {active}")
    print("Switch:            hey-claude agent use <preset>")
    print("Full control:      hey-claude config set launch_template '<command with {command}>'")
    print("Placeholders:      {command} {name} {permission_mode} {model} {claude_bin}")
    return 0


def cmd_app(args: argparse.Namespace) -> int:
    dest = Path(args.dest).expanduser() if args.dest else None
    return appbundle.build_and_report(dest)


def cmd_install(args): return service.install()
def cmd_start(args): return service.start()
def cmd_stop(args): return service.stop()
def cmd_status(args): return service.status()


def cmd_uninstall(args: argparse.Namespace) -> int:
    if getattr(args, "all", False):
        return service.purge(assume_yes=getattr(args, "yes", False))
    rc = service.uninstall()
    print("  tip: full teardown (config, trained models, .app) →  hey-claude uninstall --all")
    return rc


_SOUND_EVENTS = {
    "wake": ("sound_wake", "before — plays when the wake word fires"),
    "endpoint": ("sound_endpoint", "endpoint — plays when you stop talking / capture ends"),
    "dispatch": ("sound_dispatch", "after — plays when an agent is dispatched"),
    "cancel": ("sound_cancel", "wake fired but no command / cancelled"),
    "error": ("sound_error", "dispatch failed"),
}


def cmd_sounds(args: argparse.Namespace) -> int:
    import time as _time

    from . import sounds

    action = args.sounds_action
    cfg = Config.load()

    if action in (None, "list"):
        avail = sounds.catalog_paths()
        print("Sound catalog (built-in macOS sounds) — assign with `hey-claude sounds set <event> <name>`:\n")
        for role in ("before", "endpoint", "after", "cancel", "error"):
            names = [n for n, (r, _) in sounds.CATALOG.items() if r == role and n in avail]
            if names:
                print(f"  {role}:")
                for n in names:
                    print(f"    {n:<11} {sounds.CATALOG[n][1]}")
        print("\nCurrently assigned:")
        for ev, (field, desc) in _SOUND_EVENTS.items():
            val = getattr(cfg, field) or f"(default: {sounds.DEFAULTS[ev].stem})"
            print(f"  {ev:<9} {val:<22} {desc}")
        print("\nPreview one:  hey-claude sounds play Glass")
        print("Use a file:   hey-claude sounds set dispatch /path/to/sound.wav")
        print("Silence one:  hey-claude sounds set cancel none")
        return 0

    if action == "play":
        path = sounds.resolve("wake", args.name)
        if path is None:
            print(f"✗ no sound resolved for {args.name!r} (try a catalog name like Glass, or a file path)")
            return 1
        print(f"♪ {path}")
        sounds.play(path, True)
        _time.sleep(2)
        return 0

    if action == "set":
        if args.event not in _SOUND_EVENTS:
            print(f"✗ event must be one of: {', '.join(_SOUND_EVENTS)}")
            return 1
        field = _SOUND_EVENTS[args.event][0]
        cfg.set_field(field, args.name)
        resolved = sounds.resolve(args.event, args.name)
        cfg.save()
        note = f"→ {resolved}" if resolved else "(silenced)" if args.name.lower() in ("none", "off") else "(not found — will fall back silent)"
        print(f"✓ {args.event} sound = {args.name!r}  {note}")
        if resolved:
            sounds.play(resolved, True)
            _time.sleep(2)
        return 0

    if action == "test":
        for ev in ("wake", "endpoint", "dispatch", "cancel", "error"):
            field = _SOUND_EVENTS[ev][0]
            path = sounds.resolve(ev, getattr(cfg, field))
            print(f"  {ev:<9} {path}")
            sounds.play(path, True)
            _time.sleep(1.3)
        return 0
    return 1


def cmd_config(args: argparse.Namespace) -> int:
    action = args.config_action
    if action == "path":
        print(config_path())
        return 0
    if action == "init":
        path = Config.load().save()
        print(f"✓ wrote {path}")
        return 0
    if action == "show":
        cfg = Config.load()
        for f in fields(cfg):
            print(f"{f.name} = {getattr(cfg, f.name)!r}")
        return 0
    if action == "get":
        cfg = Config.load()
        if not hasattr(cfg, args.key):
            print(f"✗ unknown key: {args.key}", file=sys.stderr)
            return 1
        print(getattr(cfg, args.key))
        return 0
    if action == "set":
        cfg = Config.load()
        try:
            cfg.set_field(args.key, args.value)
        except KeyError:
            print(f"✗ unknown key: {args.key}", file=sys.stderr)
            return 1
        except ValueError as exc:
            print(f"✗ bad value: {exc}", file=sys.stderr)
            return 1
        path = cfg.save()
        print(f"✓ {args.key} = {getattr(cfg, args.key)!r}  ({path})")
        return 0
    if action == "edit":
        import os
        import subprocess
        path = Config.load().save()  # ensure it exists
        editor = os.environ.get("EDITOR", "nano")
        subprocess.run([editor, str(path)])
        return 0
    return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hey-claude",
        description='Say "Hey Claude, <task>" to dispatch a Claude Code agent. Fully on-device.',
    )
    p.add_argument("-V", "--version", action="version", version=f"hey-claude {__version__}")
    sub = p.add_subparsers(dest="command")

    def add_run_flags(rp: argparse.ArgumentParser) -> None:
        rp.add_argument("--engine", choices=["openwakeword", "whisper"], help="wake engine for this run")
        rp.add_argument("--launch", choices=["bg", "terminal", "print"], help="how to launch the agent")
        rp.add_argument("--threshold", type=float, help="openWakeWord detection threshold (0-1)")
        rp.add_argument("--whisper-model", dest="whisper_model", help="MLX Whisper model for command transcription")
        rp.add_argument("--device", help="microphone device (index or name substring)")
        rp.add_argument("--permission-mode", dest="permission_mode", help="permission mode for dispatched agents")
        rp.add_argument("--model", dest="claude_model", help="model for dispatched agents")
        rp.add_argument("--confirm", action="store_true", help="require Enter before each dispatch")
        rp.add_argument("--no-chime", dest="no_chime", action="store_true", help="disable audible feedback")
        rp.add_argument("--quiet", action="store_true", help="suppress status output")

    run_p = sub.add_parser("run", aliases=["listen"], help="start listening (default)")
    add_run_flags(run_p)
    run_p.set_defaults(func=cmd_run)

    sub.add_parser("doctor", help="check the environment and guide first-run setup").set_defaults(func=cmd_doctor)

    train_p = sub.add_parser("train", help="get a free 'hey claude' wake-word model (no mic)")
    train_p.add_argument("--no-open", action="store_true", help="don't open the browser")
    train_p.set_defaults(func=cmd_train)

    im_p = sub.add_parser("import-model", help="install a downloaded .onnx/.tflite wake-word model")
    im_p.add_argument("path")
    im_p.add_argument("--name", help="store under this name (default: source filename)")
    im_p.add_argument("--no-activate", action="store_true", help="install without making it active")
    im_p.set_defaults(func=cmd_import_model)

    models_p = sub.add_parser("models", help="list / switch installed wake-word models")
    models_sub = models_p.add_subparsers(dest="models_action")
    use_p = models_sub.add_parser("use", help="activate an installed model by name")
    use_p.add_argument("name")
    models_p.set_defaults(func=cmd_models)

    agent_p = sub.add_parser("agent", help="choose which agent a heard command launches")
    agent_sub = agent_p.add_subparsers(dest="agent_action")
    agent_sub.add_parser("list", help="list agent presets and the active one")
    agent_sub.add_parser("show", help="print the active agent")
    au = agent_sub.add_parser("use", help="switch to an agent preset (claude-bg, codex, aider, …)")
    au.add_argument("name")
    agent_p.set_defaults(func=cmd_agent)

    snd_p = sub.add_parser("sounds", help="browse / preview / assign earcons")
    snd_sub = snd_p.add_subparsers(dest="sounds_action")
    snd_sub.add_parser("list", help="show the catalog and current assignments")
    sp = snd_sub.add_parser("play", help="preview a sound by catalog name or file path"); sp.add_argument("name")
    ss = snd_sub.add_parser("set", help="assign a sound to an event")
    ss.add_argument("event", help="wake | endpoint | dispatch | cancel | error")
    ss.add_argument("name", help="catalog name, file path, system-sound name, or 'none'")
    snd_sub.add_parser("test", help="play all four currently-assigned event sounds")
    snd_p.set_defaults(func=cmd_sounds)

    app_p = sub.add_parser("app", help="build a .app wrapper (stable mic permission)")
    app_p.add_argument("dest", nargs="?", help="output path (default: ~/Applications/Hey Claude.app)")
    app_p.set_defaults(func=cmd_app)

    sub.add_parser("install", help="install the launchd agent (listen at login)").set_defaults(func=cmd_install)
    un_p = sub.add_parser("uninstall", help="remove the launchd agent (use --all for full teardown)")
    un_p.add_argument("--all", action="store_true",
                      help="also remove config, trained models, and the .app bundle")
    un_p.add_argument("-y", "--yes", action="store_true",
                      help="skip the confirmation prompt (with --all)")
    un_p.set_defaults(func=cmd_uninstall)
    sub.add_parser("start", help="start the launchd agent").set_defaults(func=cmd_start)
    sub.add_parser("stop", help="stop the launchd agent").set_defaults(func=cmd_stop)
    sub.add_parser("status", help="launchd agent status").set_defaults(func=cmd_status)

    cfg_p = sub.add_parser("config", help="view or change configuration")
    cfg_sub = cfg_p.add_subparsers(dest="config_action", required=True)
    cfg_sub.add_parser("path")
    cfg_sub.add_parser("show")
    cfg_sub.add_parser("init")
    cfg_sub.add_parser("edit")
    g = cfg_sub.add_parser("get"); g.add_argument("key")
    s = cfg_sub.add_parser("set"); s.add_argument("key"); s.add_argument("value")
    cfg_p.set_defaults(func=cmd_config)

    # Bare `hey-claude` => run with default (no override) flags.
    p.set_defaults(func=cmd_run, engine=None, launch=None, threshold=None,
                   whisper_model=None, device=None, permission_mode=None,
                   claude_model=None, confirm=False, no_chime=False, quiet=False)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", cmd_run)
    try:
        return func(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
