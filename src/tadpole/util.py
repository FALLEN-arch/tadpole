"""Pure helpers with no GUI dependency (so they are easy to unit test)."""
from __future__ import annotations

import re
import shlex

NAME_RE = re.compile(r"[A-Za-z0-9_]{1,40}")

# Commands that talk to the tool itself rather than to one device.
GLOBAL_ADB = ("devices", "version", "--version")
GLOBAL_FASTBOOT = ("devices", "--version")


def flash_pct(line, st):
    """Estimate flash progress (0-100) from a fastboot output line, or None."""
    m = re.search(r"Sending sparse '[^']*' (\d+)/(\d+)", line)
    if m:
        st["i"], st["n"] = int(m.group(1)), int(m.group(2))
        return (st["i"] - 0.5) / st["n"] * 100
    if line.startswith("Sending"):
        return (st["i"] - 0.5) / st["n"] * 100
    if line.startswith("Writing"):
        return st["i"] / st["n"] * 100
    if line.startswith("Finished"):
        return 100.0
    return None


def human(n: int) -> str:
    if not n:
        return "-"
    for u in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or u == "TiB":
            return f"{n:.0f} {u}" if n >= 10 or u == "B" else f"{n:.1f} {u}"
        n /= 1024


def parse_terminal(raw: str, mode: str, selected: str | None):
    """Interpret a line typed into the terminal dock.

    ``mode`` is "adb" or "fb" (the GUI mode); a leading ``adb`` / ``fastboot``
    word overrides it. An explicit ``-s SERIAL`` is honoured instead of the
    device selected in the GUI. Returns ``(tool, serial, args)`` where tool is
    "adb" or "fb" and serial is None for tool-level commands such as
    ``devices``, or ``None`` when the line is empty. Raises ValueError with a
    user-facing message for bad input.
    """
    a = shlex.split(raw)
    tool = mode
    if a and a[0] in ("adb", "fastboot"):
        tool = "adb" if a.pop(0) == "adb" else "fb"
    serial = selected
    if a and a[0] == "-s":
        if len(a) < 3 or not a[1]:
            raise ValueError("Expected a device serial after -s.")
        serial = a[1]
        del a[:2]
    if not a:
        return None
    global_cmds = GLOBAL_ADB if tool == "adb" else GLOBAL_FASTBOOT
    return tool, (None if a[0] in global_cmds else serial), a
