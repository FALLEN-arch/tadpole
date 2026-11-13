"""Fastboot service - business logic for fastboot operations."""
from __future__ import annotations

import re
import shutil
import subprocess
import threading
from typing import Optional, Callable

from ..models.fastboot import FastbootVariables
from ..models.partition import Partition, PartitionType
from ..models.flash import FlashOptions


class FastbootError(RuntimeError):
    """Fastboot operation error."""
    pass


class FastbootService:
    """Service for fastboot operations. Stateless, uses only serial for targeting."""

    def __init__(self, fastboot_path: Optional[str] = None):
        self._fastboot_path = fastboot_path or shutil.which("fastboot")
        if not self._fastboot_path:
            raise FastbootError(
                "fastboot not found on PATH. Install Android Platform Tools "
                "and make sure the fastboot binary is on your PATH."
            )

    @property
    def fastboot_path(self) -> str:
        return self._fastboot_path

    def _argv(self, serial: Optional[str], args: list[str]) -> list[str]:
        argv = [self._fastboot_path]
        if serial:
            argv.extend(["-s", serial])
        argv.extend(args)
        return argv

    def run(self, serial: Optional[str], args: list[str], timeout: float = 120) -> str:
        """Run fastboot and return combined stdout+stderr."""
        argv = self._argv(serial, args)
        proc = subprocess.run(argv, capture_output=True, timeout=timeout)
        out = (proc.stdout + proc.stderr).decode("utf-8", "replace").strip()
        if proc.returncode != 0:
            raise FastbootError(out or f"fastboot exited with code {proc.returncode}")
        return out

    def run_stream(
        self,
        serial: Optional[str],
        args: list[str],
        on_line: Callable[[str], None],
        timeout: float = 1800,
    ) -> str:
        """Run fastboot with streaming output for progress tracking."""
        argv = self._argv(serial, args)
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
        timed_out = threading.Event()

        def _kill():
            timed_out.set()
            proc.kill()

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

    def version(self) -> str:
        return self.run(None, ["--version"]).splitlines()[0]

    def list_devices(self) -> list[dict]:
        """List fastboot devices."""
        result = []
        for line in self.run(None, ["devices"]).splitlines():
            line = line.strip()
            if not line or line.startswith("<") or line.lower().startswith("no permissions"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                result.append({"serial": parts[0], "state": parts[1]})
        return result

    def get_variables(self, serial: str) -> FastbootVariables:
        """Get all fastboot variables."""
        out = self.run(serial, ["getvar", "all"], timeout=60)
        return self._parse_variables(out)

    def _parse_variables(self, out: str) -> FastbootVariables:
        """Parse `fastboot getvar all` output."""
        _LINE = re.compile(r"^(.+?):\s+(.*)$")
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
                name = key.split(":", 1)[1]
                partitions.setdefault(name, {"name": name})["logical"] = value == "yes"
            elif key != "all":
                variables[key] = value
        partition_list = [
            Partition.from_fastboot_dict(p) for p in sorted(partitions.values(), key=lambda p: p["name"])
        ]
        return FastbootVariables(variables=variables, partitions=partition_list)

    def flash(self, serial: str, options: FlashOptions, on_progress: Optional[Callable[[int], None]] = None) -> str:
        """Flash an image with progress callback."""
        args = options.to_fastboot_args()
        st = {"i": 1, "n": 1}

        def progress(line: str) -> None:
            pct = self._estimate_progress(line, st)
            if pct is not None and on_progress:
                on_progress(int(pct))

        return self.run_stream(serial, args, progress, timeout=1800)

    def _estimate_progress(self, line: str, st: dict) -> Optional[float]:
        """Estimate flash progress (0-100) from a fastboot output line."""
        import re
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

    # --- Partition operations ---

    def erase_partition(self, serial: str, partition: str) -> str:
        """Erase a partition."""
        return self.run(serial, ["erase", partition])

    def flash_partition(self, serial: str, partition: str, image: str) -> str:
        """Flash a partition (simple version)."""
        return self.run(serial, ["flash", partition, image], timeout=300)

    # --- Bootloader ---

    def unlock(self, serial: str) -> str:
        """Unlock bootloader."""
        return self.run(serial, ["flashing", "unlock"])

    def lock(self, serial: str) -> str:
        """Lock bootloader."""
        return self.run(serial, ["flashing", "lock"])

    def wipe(self, serial: str) -> str:
        """Wipe userdata and cache (-w)."""
        return self.run(serial, ["-w"])

    def set_active_slot(self, serial: str, slot: str) -> str:
        """Set active boot slot."""
        return self.run(serial, ["set_active", slot])

    # --- Reboot ---

    def reboot(self, serial: str, target: str = "") -> str:
        """Reboot device."""
        args = ["reboot"]
        if target:
            args.append(target)
        return self.run(serial, args)

    def reboot_bootloader(self, serial: str) -> str:
        return self.reboot(serial, "bootloader")

    def reboot_recovery(self, serial: str) -> str:
        return self.reboot(serial, "recovery")

    def reboot_fastbootd(self, serial: str) -> str:
        return self.reboot(serial, "fastboot")

    def reboot_system(self, serial: str) -> str:
        return self.reboot(serial)
