"""Thin, safe wrapper around the fastboot binary (argv lists, never a shell)."""
from __future__ import annotations

import re
import shutil
import subprocess
import threading


class FastbootError(RuntimeError):
    pass


def fastboot_path() -> str:
    path = shutil.which("fastboot")
    if not path:
        raise FastbootError(
            "fastboot not found on PATH. Install Android Platform Tools "
            "and make sure the fastboot binary is on your PATH."
        )
    return path


def run(serial: str | None, args: list[str], timeout: float = 120) -> str:
    """Run fastboot and return stdout+stderr (fastboot prints progress to stderr)."""
    argv = [fastboot_path()]
    if serial:
        argv.extend(["-s", serial])
    argv.extend(args)
    proc = subprocess.run(argv, capture_output=True, timeout=timeout)
    out = (proc.stdout + proc.stderr).decode("utf-8", "replace").strip()
    if proc.returncode != 0:
        raise FastbootError(out or f"fastboot exited with code {proc.returncode}")
    return out


def version() -> str:
    output = run(None, ["--version"]).strip()
    return output.splitlines()[0] if output else "Fastboot version unavailable"


def devices() -> list[dict]:
    result = []
    for line in run(None, ["devices"]).splitlines():
        line = line.strip()
        # skip "< waiting for any device >" and udev "no permissions ..." noise
        if not line or line.startswith("<") or line.lower().startswith("no permissions"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            result.append({"serial": parts[0], "state": parts[1]})
    return result


_LINE = re.compile(r"^(.+?):\s+(.*)$")


def getvar_all(serial: str) -> dict:
    out = run(serial, ["getvar", "all"], timeout=60)
    variables: dict[str, str] = {}
    partitions: dict[str, dict] = {}
    for raw in out.splitlines():
        line = raw.strip()
        if line.startswith("(bootloader)"):
            line = line[len("(bootloader)"):].strip()
        match = _LINE.match(line)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
        if key.startswith("Finished"):
            continue
        if key.startswith("partition-size:"):
            name = key.split(":", 1)[1]
            try:
                size = int(value, 16)
            except ValueError:
                size = 0
            partitions.setdefault(name, {"name": name})["size"] = size
        elif key.startswith("is-logical:"):
            partitions.setdefault(key.split(":", 1)[1], {"name": key.split(":", 1)[1]})["logical"] = value == "yes"
        elif key != "all":
            variables[key] = value
    return {
        "vars": variables,
        "partitions": sorted(partitions.values(), key=lambda p: p["name"]),
    }


def run_stream(serial, args, on_line, timeout: float = 1800) -> str:
    """Like run(), but calls on_line(text) for every output line (flash progress)."""
    argv = [fastboot_path()]
    if serial:
        argv.extend(["-s", serial])
    argv.extend(args)
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
    timed_out = threading.Event()

    def _kill():
        timed_out.set()
        proc.kill()

    # The read loop below blocks until fastboot closes its output, so the
    # timeout has to be enforced from a timer, not from proc.wait().
    timer = threading.Timer(timeout, _kill)
    timer.daemon = True
    timer.start()
    lines: list[str] = []
    try:
        assert proc.stdout is not None
        for raw in iter(proc.stdout.readline, b""):
            line = raw.decode("utf-8", "replace").rstrip()
            lines.append(line)
            on_line(line)
        proc.wait()
    finally:
        timer.cancel()
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    if timed_out.is_set():
        raise FastbootError("fastboot timed out")
    out = "\n".join(lines).strip()
    if proc.returncode != 0:
        raise FastbootError(out or f"fastboot exited with code {proc.returncode}")
    return out
