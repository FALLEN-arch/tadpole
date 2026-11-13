"""Thin, safe wrapper around the adb binary.

Every call builds an argv list and never uses a shell, so device serials,
package names, and paths cannot be interpreted as shell syntax.
"""
from __future__ import annotations

import re
import shutil
import subprocess

class AdbError(RuntimeError):
    pass

def adb_path() -> str:
    path = shutil.which("adb")
    if not path:
        raise AdbError(
            "adb not found on PATH. Install Android Platform Tools "
            "and make sure the adb binary is on your PATH."
        )
    return path

def _argv(serial: str | None, args: list[str]) -> list[str]:
    argv = [adb_path()]
    if serial:
        argv.extend(["-s", serial])
    argv.extend(args)
    return argv

def _fail(proc: subprocess.CompletedProcess, text_stdout: bool = True) -> AdbError:
    """Build an AdbError from a failed process.

    Falls back to stdout when stderr is empty (e.g. `adb shell grep` with no
    match, or commands that print their error on stdout) so the message is
    never just an exit code when there is real output to show.
    """
    msg = proc.stderr.decode("utf-8", "replace").strip()
    if not msg and text_stdout:
        msg = proc.stdout.decode("utf-8", "replace").strip()
    return AdbError(msg or f"adb exited with code {proc.returncode}")

def run(serial: str | None, args: list[str], timeout: float = 60) -> str:
    """Run adb and return stdout as text. Raises AdbError on non-zero exit."""
    proc = subprocess.run(
        _argv(serial, args), capture_output=True, timeout=timeout
    )
    if proc.returncode != 0:
        raise _fail(proc)
    return proc.stdout.decode("utf-8", "replace")

def run_bytes(serial: str | None, args: list[str], timeout: float = 60) -> bytes:
    """Run adb and return raw stdout bytes (for screenshots and downloads)."""
    proc = subprocess.run(
        _argv(serial, args), capture_output=True, timeout=timeout
    )
    if proc.returncode != 0:
        raise _fail(proc, text_stdout=False)
    return proc.stdout

def stream(serial: str | None, args: list[str]):
    """Yield stdout lines from a long-running adb process (logcat, screenrecord)."""
    proc = subprocess.Popen(
        _argv(serial, args),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
    )
    try:
        assert proc.stdout is not None
        for raw in proc.stdout:
            yield raw.decode("utf-8", "replace").rstrip("\r\n")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

def devices() -> list[dict]:
    out = run(None, ["devices", "-l"])
    result: list[dict] = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices") or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        extra: dict[str, str] = {}
        for token in parts[2:]:
            if ":" in token:
                key, value = token.split(":", 1)
                extra[key] = value
        result.append(
            {
                "serial": serial,
                "state": state,
                "model": extra.get("model", ""),
                "product": extra.get("product", ""),
                "device": extra.get("device", ""),
                "transport_id": extra.get("transport_id", ""),
            }
        )
    return result

def prop(serial: str, key: str) -> str:
    try:
        return run(serial, ["shell", "getprop", key]).strip()
    except AdbError:
        return ""

def device_info(serial: str) -> dict:
    return {
        "serial": serial,
        "model": prop(serial, "ro.product.model"),
        "brand": prop(serial, "ro.product.brand"),
        "android": prop(serial, "ro.build.version.release"),
        "sdk": prop(serial, "ro.build.version.sdk"),
        "abi": prop(serial, "ro.product.cpu.abi"),
    }

def battery(serial: str) -> dict:
    try:
        out = run(serial, ["shell", "dumpsys", "battery"])
    except AdbError:
        return {}
    info: dict[str, str] = {}
    for line in out.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            info[key.strip()] = value.strip()
    status_map = {
        "1": "Unknown",
        "2": "Charging",
        "3": "Discharging",
        "4": "Not charging",
        "5": "Full",
    }
    level = info.get("level", "")
    temp = info.get("temperature", "")
    temp_text = f"{int(temp) / 10:.1f} C" if temp.isdigit() else ""
    return {
        "level": f"{level}%" if level else "",
        "status": status_map.get(info.get("status", ""), info.get("status", "")),
        "temperature": temp_text,
    }

def screen_size(serial: str) -> str:
    try:
        out = run(serial, ["shell", "wm", "size"])
    except AdbError:
        return ""
    match = re.search(r"(\d+x\d+)", out)
    return match.group(1) if match else ""


_SNAP_CMD = (
    "echo @@P; getprop ro.product.model; getprop ro.product.brand; "
    "getprop ro.build.version.release; getprop ro.build.version.sdk; "
    "getprop ro.product.cpu.abi; echo @@B; dumpsys battery; echo @@W; wm size"
)


def snapshot(serial: str) -> tuple[dict, dict, str]:
    """Overview data in ONE adb call. Returns (device_info, battery, screen_size).

    Falls back to the older per-property calls if anything looks off.
    """
    try:
        out = run(serial, ["shell", _SNAP_CMD], timeout=30)
        sec: dict[str, list[str]] = {}
        cur = None
        for line in out.splitlines():
            line = line.strip()
            if line in ("@@P", "@@B", "@@W"):
                cur = line
                sec[cur] = []
            elif cur:
                sec[cur].append(line)
        p = (sec.get("@@P", []) + [""] * 5)[:5]
        info = {"serial": serial, "model": p[0], "brand": p[1], "android": p[2], "sdk": p[3], "abi": p[4]}
        b: dict[str, str] = {}
        for line in sec.get("@@B", []):
            if ":" in line:
                k, v = line.split(":", 1)
                b[k.strip()] = v.strip()
        status_map = {"1": "Unknown", "2": "Charging", "3": "Discharging", "4": "Not charging", "5": "Full"}
        lvl, tmp = b.get("level", ""), b.get("temperature", "")
        bat = {
            "level": f"{lvl}%" if lvl else "",
            "status": status_map.get(b.get("status", ""), b.get("status", "")),
            "temperature": f"{int(tmp) / 10:.1f} C" if tmp.isdigit() else "",
        }
        m = re.search(r"(\d+x\d+)", " ".join(sec.get("@@W", [])))
        if not info["model"] and not bat["level"]:
            raise AdbError("empty snapshot")
        return info, bat, (m.group(1) if m else "")
    except Exception:  # noqa: BLE001
        return device_info(serial), battery(serial), screen_size(serial)
