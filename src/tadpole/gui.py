"""Command-line entry point (``tadpole``). Kept free of Tk imports so it can report problems first."""
from __future__ import annotations

import argparse
import sys


def _version() -> str:
    try:
        from importlib.metadata import version
        return version("tadpole")
    except Exception:  # noqa: BLE001
        from . import __version__
        return __version__


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tadpole", description="Desktop GUI for adb and fastboot.")
    p.add_argument("--version", action="version", version=f"tadpole {_version()}")
    p.add_argument("--check", action="store_true", help="check dependencies (Tk, tkinterdnd2, adb, fastboot) and exit")
    p.add_argument("--install-desktop", action="store_true", help="add Tadpole to the application menu (current user)")
    p.add_argument("--uninstall-desktop", action="store_true", help="remove the application menu entry and icon")
    return p


def main(argv: list[str] | None = None) -> None:
    from . import deps

    args = build_parser().parse_args(argv)
    if args.install_desktop or args.uninstall_desktop:
        from . import desktop
        done = desktop.install() if args.install_desktop else desktop.uninstall()
        print(("Installed:" if args.install_desktop else "Removed:") if done else "Nothing to do.")
        for path in done:
            print(f"  {path}")
        return
    py_problems = deps.python_problems()
    missing = deps.missing_tools()
    if args.check:
        for msg in py_problems:
            print(f"MISSING  {msg}")
        if missing:
            print("MISSING  " + deps.tools_message(missing))
        if not (py_problems or missing):
            print("OK: Tk, tkinterdnd2, adb and fastboot are all available.")
        sys.exit(1 if (py_problems or missing) else 0)
    if py_problems:
        raise SystemExit("Tadpole cannot start:\n  " + "\n  ".join(py_problems))
    from .app import main as run_app
    run_app()


if __name__ == "__main__":
    main()
