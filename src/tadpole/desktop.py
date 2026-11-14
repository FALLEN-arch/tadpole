"""Install / remove the per-user launcher (application menu entry + icon). Linux only."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"
ICON_SIZE = 256


def _data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def paths() -> tuple[Path, Path]:
    """(desktop file, icon file) locations for the current user."""
    base = _data_home()
    return (base / "applications" / "tadpole.desktop",
            base / "icons" / "hicolor" / f"{ICON_SIZE}x{ICON_SIZE}" / "apps" / "tadpole.png")


def launch_command() -> str:
    """Exec line for the .desktop file: the tadpole script next to this Python, else ``python -m tadpole``."""
    script = Path(sys.executable).parent / "tadpole"
    if script.is_file():
        return f'"{script}"'
    return f'"{sys.executable}" -m tadpole'


def desktop_entry(exec_line: str) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Tadpole\n"
        "Comment=Desktop GUI for adb and fastboot\n"
        f"Exec={exec_line}\n"
        "Icon=tadpole\n"
        "Terminal=false\n"
        "Categories=Development;Utility;\n"
        "StartupWMClass=Tadpole\n"
    )


def install() -> list[Path]:
    desktop, icon = paths()
    icon.parent.mkdir(parents=True, exist_ok=True)
    desktop.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ASSETS / f"tadpole-{ICON_SIZE}.png", icon)
    desktop.write_text(desktop_entry(launch_command()), encoding="utf-8")
    return [desktop, icon]


def uninstall() -> list[Path]:
    removed = []
    for p in paths():
        if p.exists():
            p.unlink()
            removed.append(p)
    return removed
