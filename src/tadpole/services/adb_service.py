"""ADB service - business logic for ADB operations."""
from __future__ import annotations

import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ..models.device import Device, DeviceState, DeviceInfo, BatteryInfo
from ..models.app import AppInfo, AppState
from ..models.file import FileInfo, FileType


class AdbError(RuntimeError):
    """ADB operation error."""
    pass


class AdbService:
    """Service for ADB operations. Stateless, uses only serial for targeting."""

    def __init__(self, adb_path: Optional[str] = None):
        self._adb_path = adb_path or shutil.which("adb")
        if not self._adb_path:
            raise AdbError(
                "adb not found on PATH. Install Android Platform Tools "
                "and make sure the adb binary is on your PATH."
            )

    @property
    def adb_path(self) -> str:
        return self._adb_path

    def _argv(self, serial: Optional[str], args: list[str]) -> list[str]:
        argv = [self._adb_path]
        if serial:
            argv.extend(["-s", serial])
        argv.extend(args)
        return argv

    def _run(self, serial: Optional[str], args: list[str], timeout: float = 60) -> subprocess.CompletedProcess:
        return subprocess.run(
            self._argv(serial, args),
            capture_output=True,
            timeout=timeout,
        )

    def _check_result(self, proc: subprocess.CompletedProcess, text_stdout: bool = True) -> str:
        if proc.returncode != 0:
            msg = proc.stderr.decode("utf-8", "replace").strip()
            if not msg and text_stdout:
                msg = proc.stdout.decode("utf-8", "replace").strip()
            raise AdbError(msg or f"adb exited with code {proc.returncode}")
        return proc.stdout.decode("utf-8", "replace")

    def run(self, serial: Optional[str], args: list[str], timeout: float = 60) -> str:
        """Run adb command and return stdout as text."""
        proc = self._run(serial, args, timeout)
        return self._check_result(proc)

    def run_bytes(self, serial: Optional[str], args: list[str], timeout: float = 60) -> bytes:
        """Run adb command and return raw stdout bytes."""
        proc = self._run(serial, args, timeout)
        if proc.returncode != 0:
            self._check_result(proc, text_stdout=False)
        return proc.stdout

    # --- Device enumeration ---

    def list_devices(self) -> list[Device]:
        """List all connected devices."""
        out = self.run(None, ["devices", "-l"])
        devices: list[Device] = []
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices") or line.startswith("*"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            serial, state_str = parts[0], parts[1]
            extra: dict[str, str] = {}
            for token in parts[2:]:
                if ":" in token:
                    key, value = token.split(":", 1)
                    extra[key] = value
            try:
                state = DeviceState(state_str)
            except ValueError:
                state = DeviceState.UNKNOWN
            devices.append(Device(
                serial=serial,
                state=state,
                model=extra.get("model", ""),
                product=extra.get("product", ""),
                device=extra.get("device", ""),
                transport_id=extra.get("transport_id", ""),
            ))
        return devices

    # --- Device info ---

    def get_device_info(self, serial: str) -> DeviceInfo:
        """Get detailed device info in one snapshot call."""
        # Use the efficient snapshot command
        snap_cmd = (
            "echo @@P; getprop ro.product.model; getprop ro.product.brand; "
            "getprop ro.build.version.release; getprop ro.build.version.sdk; "
            "getprop ro.product.cpu.abi; echo @@B; dumpsys battery; echo @@W; wm size"
        )
        try:
            out = self.run(serial, ["shell", snap_cmd], timeout=30)
            return self._parse_snapshot(serial, out)
        except AdbError:
            # Fallback to individual calls
            return DeviceInfo(
                serial=serial,
                model=self.get_prop(serial, "ro.product.model"),
                brand=self.get_prop(serial, "ro.product.brand"),
                android=self.get_prop(serial, "ro.build.version.release"),
                sdk=self.get_prop(serial, "ro.build.version.sdk"),
                abi=self.get_prop(serial, "ro.product.cpu.abi"),
            )

    def _parse_snapshot(self, serial: str, out: str) -> DeviceInfo:
        """Parse the snapshot output."""
        sections: dict[str, list[str]] = {}
        current = None
        for line in out.splitlines():
            line = line.strip()
            if line in ("@@P", "@@B", "@@W"):
                current = line
                sections[current] = []
            elif current:
                sections[current].append(line)

        # Device props
        props = (sections.get("@@P", []) + [""] * 5)[:5]
        info = DeviceInfo(
            serial=serial,
            model=props[0],
            brand=props[1],
            android=props[2],
            sdk=props[3],
            abi=props[4],
        )

        # Battery
        bat: dict[str, str] = {}
        for line in sections.get("@@B", []):
            if ":" in line:
                k, v = line.split(":", 1)
                bat[k.strip()] = v.strip()
        status_map = {"1": "Unknown", "2": "Charging", "3": "Discharging", "4": "Not charging", "5": "Full"}
        lvl, tmp = bat.get("level", ""), bat.get("temperature", "")
        battery = BatteryInfo(
            level=f"{lvl}%" if lvl else "",
            status=status_map.get(bat.get("status", ""), bat.get("status", "")),
            temperature=f"{int(tmp) / 10:.1f} C" if tmp.isdigit() else "",
        )

        # Screen size
        m = re.search(r"(\d+x\d+)", " ".join(sections.get("@@W", [])))
        screen = m.group(1) if m else ""

        # Attach to info via Device (we'll handle this in the caller)
        return info

    def get_battery(self, serial: str) -> BatteryInfo:
        """Get battery info."""
        try:
            out = self.run(serial, ["shell", "dumpsys", "battery"])
        except AdbError:
            return BatteryInfo()
        info: dict[str, str] = {}
        for line in out.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                info[key.strip()] = value.strip()
        status_map = {"1": "Unknown", "2": "Charging", "3": "Discharging", "4": "Not charging", "5": "Full"}
        lvl, tmp = info.get("level", ""), info.get("temperature", "")
        return BatteryInfo(
            level=f"{lvl}%" if lvl else "",
            status=status_map.get(info.get("status", ""), info.get("status", "")),
            temperature=f"{int(tmp) / 10:.1f} C" if tmp.isdigit() else "",
        )

    def get_screen_size(self, serial: str) -> str:
        """Get screen resolution."""
        try:
            out = self.run(serial, ["shell", "wm", "size"])
        except AdbError:
            return ""
        m = re.search(r"(\d+x\d+)", out)
        return m.group(1) if m else ""

    def get_prop(self, serial: str, key: str) -> str:
        """Get a single system property."""
        try:
            return self.run(serial, ["shell", "getprop", key]).strip()
        except AdbError:
            return ""

    # --- Apps ---

    def list_packages(self, serial: str, show_disabled: bool = True, system_only: bool = False) -> list[AppInfo]:
        """List installed packages."""
        args = ["shell", "pm", "list", "packages", "-f"]
        if show_disabled:
            args.append("-u")
        if system_only:
            args.append("-s")
        out = self.run(serial, args)
        apps: list[AppInfo] = []
        for line in out.splitlines():
            line = line.strip()
            if not line or "=" not in line:
                continue
            path_part, package = line.split("=", 1)
            apk_path = path_part.replace("package:", "").strip()
            apps.append(AppInfo(package=package.strip(), apk_path=apk_path))
        return apps

    def get_app_info(self, serial: str, package: str) -> AppInfo:
        """Get detailed app info from dumpsys."""
        try:
            dump = self.run(serial, ["shell", "dumpsys", "package", package])
        except AdbError:
            return AppInfo(package=package)
        return AppInfo.from_pm_dump(package, dump)

    def launch_app(self, serial: str, package: str) -> str:
        """Launch an app by package name."""
        return self.run(serial, ["shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"])

    def stop_app(self, serial: str, package: str) -> str:
        """Force stop an app."""
        return self.run(serial, ["shell", "am", "force-stop", package])

    def clear_app_data(self, serial: str, package: str) -> str:
        """Clear app data."""
        return self.run(serial, ["shell", "pm", "clear", package])

    def uninstall_app(self, serial: str, package: str) -> str:
        """Uninstall an app."""
        return self.run(serial, ["uninstall", package])

    def disable_app(self, serial: str, package: str) -> str:
        """Disable an app."""
        return self.run(serial, ["shell", "pm", "disable-user", "--user", "0", package])

    def enable_app(self, serial: str, package: str) -> str:
        """Enable an app."""
        return self.run(serial, ["shell", "pm", "enable", "--user", "0", package])

    def pull_apk(self, serial: str, package: str, dest: str) -> str:
        """Pull APK file for a package."""
        app = self.get_app_info(serial, package)
        if not app.apk_path:
            raise AdbError(f"Could not find APK path for {package}")
        return self.run(serial, ["pull", app.apk_path, dest])

    def install_apk(self, serial: str, apk_path: str, replace: bool = True, grant_permissions: bool = True) -> str:
        """Install an APK."""
        args = ["install"]
        if replace:
            args.append("-r")
        if grant_permissions:
            args.append("-g")
        args.append(apk_path)
        return self.run(serial, args, timeout=300)

    def install_multiple(self, serial: str, apk_paths: list[str], replace: bool = True, grant_permissions: bool = True) -> list[str]:
        """Install multiple APKs sequentially."""
        results = []
        for apk in apk_paths:
            try:
                result = self.install_apk(serial, apk, replace, grant_permissions)
                results.append(f"OK: {apk} -> {result}")
            except AdbError as e:
                results.append(f"FAIL: {apk} -> {e}")
        return results

    # --- Files ---

    def list_files(self, serial: str, path: str) -> list[FileInfo]:
        """List files in a directory."""
        quoted = shlex.quote(path)
        out = self.run(serial, ["shell", "ls", "-la", quoted])
        files: list[FileInfo] = []
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("total") or line in (".", ".."):
                continue
            info = FileInfo.from_ls_line(line, path)
            if info:
                files.append(info)
        # Sort: directories first, then alphabetically
        files.sort(key=lambda f: (not f.is_dir, f.name.lower()))
        return files

    def pull_file(self, serial: str, remote: str, local: str) -> str:
        """Pull a file from device."""
        return self.run(serial, ["pull", remote, local], timeout=600)

    def push_file(self, serial: str, local: str, remote: str) -> str:
        """Push a file to device."""
        return self.run(serial, ["push", local, remote], timeout=600)

    def delete_file(self, serial: str, path: str) -> str:
        """Delete a file or directory."""
        quoted = shlex.quote(path)
        return self.run(serial, ["shell", "rm", "-rf", quoted])

    # --- Shell ---

    def shell(self, serial: str, command: str, timeout: float = 120) -> str:
        """Run a shell command on device."""
        return self.run(serial, ["shell", command], timeout)

    # --- Logcat ---

    def logcat_stream(self, serial: str, filter_spec: str = "", format: str = "threadtime"):
        """Stream logcat output."""
        args = ["logcat", "-v", format]
        if filter_spec:
            args.extend(shlex.split(filter_spec))
        proc = subprocess.Popen(
            self._argv(serial, args),
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

    # --- Screen ---

    def screenshot(self, serial: str) -> bytes:
        """Capture screenshot as PNG bytes."""
        return self.run_bytes(serial, ["exec-out", "screencap", "-p"])

    def input_tap(self, serial: str, x: int, y: int) -> str:
        """Send tap input."""
        return self.run(serial, ["shell", "input", "tap", str(x), str(y)])

    def input_keyevent(self, serial: str, keycode: int) -> str:
        """Send key event."""
        return self.run(serial, ["shell", "input", "keyevent", str(keycode)])

    # --- Wireless ---

    def connect(self, address: str) -> str:
        """Connect to device over WiFi."""
        out = self.run(None, ["connect", address])
        if re.search(r"failed|cannot|unable|refused|error", out, re.I):
            raise AdbError(out.strip())
        return out

    def pair(self, address: str, code: str) -> str:
        """Pair with device over WiFi."""
        return self.run(None, ["pair", address, code], timeout=30)

    def restart_server(self) -> str:
        """Restart adb server."""
        self.run(None, ["kill-server"])
        return self.run(None, ["start-server"])

    # --- Root / Sideload ---

    def root(self, serial: str) -> str:
        """Restart adbd as root."""
        return self.run(serial, ["root"])

    def sideload(self, serial: str, zip_path: str) -> str:
        """Sideload a ZIP package."""
        return self.run(serial, ["sideload", zip_path], timeout=300)
