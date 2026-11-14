"""Startup dependency checks (no GUI imports, so they work before Tk is available)."""
from __future__ import annotations

import importlib.util
import shutil

TOOLS = ("adb", "fastboot")

_PLATFORM_TOOLS_URL = "https://developer.android.com/tools/releases/platform-tools"


def missing_tools(which=shutil.which) -> list[str]:
    """Names of required command-line tools that are not on PATH."""
    return [t for t in TOOLS if not which(t)]


def python_problems(find_spec=importlib.util.find_spec) -> list[str]:
    """User-facing messages for missing Python modules Tadpole needs to start."""
    problems = []
    if find_spec("tkinter") is None:
        problems.append("Tkinter is missing. Install your distribution's Tk package "
                        "(Debian/Ubuntu: python3-tk, Fedora: python3-tkinter, Arch: tk).")
    if find_spec("tkinterdnd2") is None:
        problems.append("tkinterdnd2 is missing (needed for drag and drop). "
                        "Install it with: pip install tkinterdnd2")
    return problems


def _distro_ids(os_release: str | None) -> set[str]:
    if os_release is None:
        try:
            with open("/etc/os-release", encoding="utf-8") as fh:
                os_release = fh.read()
        except OSError:
            return set()
    ids: set[str] = set()
    for line in os_release.splitlines():
        key, _, value = line.partition("=")
        if key in ("ID", "ID_LIKE"):
            ids.update(value.strip().strip('"').lower().split())
    return ids


def install_hint(os_release: str | None = None) -> str:
    """Best-effort install command for adb / fastboot on the current distribution."""
    ids = _distro_ids(os_release)
    if ids & {"debian", "ubuntu"}:
        return "sudo apt install adb fastboot"
    if ids & {"fedora", "rhel", "centos"}:
        return "sudo dnf install android-tools"
    if ids & {"arch", "manjaro"}:
        return "sudo pacman -S android-tools"
    if ids & {"opensuse", "suse"}:
        return "sudo zypper install android-tools"
    return f"Download Android Platform Tools from {_PLATFORM_TOOLS_URL} and add them to PATH"


def tools_message(missing: list[str], os_release: str | None = None) -> str:
    """Explain which features are unavailable and how to fix it."""
    names = " and ".join(missing)
    affected = {"adb": "ADB mode", "fastboot": "Fastboot mode"}
    features = ", ".join(affected[m] for m in missing)
    return (f"{names} not found on PATH, so {features} will not work.\n"
            f"Install: {install_hint(os_release)}\n"
            "Then press Refresh.")
