"""App-related data models."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AppState(str, Enum):
    """Application state."""
    ENABLED = "enabled"
    DISABLED = "disabled"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class AppInfo:
    """Application information."""
    package: str
    name: str = ""
    version: str = ""
    version_code: int = 0
    state: AppState = AppState.UNKNOWN
    is_system: bool = False
    installer: str = ""
    apk_path: str = ""
    data_dir: str = ""

    @property
    def display_name(self) -> str:
        return self.name or self.package

    @property
    def is_enabled(self) -> bool:
        return self.state == AppState.ENABLED

    @classmethod
    def from_dumpsys_line(cls, line: str) -> Optional[AppInfo]:
        """Parse a line from `pm list packages -f -u` or similar."""
        # Format: package:/path/to/base.apk=com.example.app
        if "=" not in line:
            return None
        path_part, package = line.split("=", 1)
        apk_path = path_part.replace("package:", "").strip()
        return cls(package=package.strip(), apk_path=apk_path)

    @classmethod
    def from_pm_dump(cls, package: str, dump: str) -> AppInfo:
        """Parse detailed package info from `dumpsys package <package>`."""
        info = {"package": package}
        for line in dump.splitlines():
            line = line.strip()
            if line.startswith("versionName="):
                info["version"] = line.split("=", 1)[1]
            elif line.startswith("versionCode="):
                try:
                    info["version_code"] = int(line.split("=", 1)[1])
                except ValueError:
                    pass
            elif "pkgFlags=" in line and "SYSTEM" in line:
                info["is_system"] = True
            elif line.startswith("installerPackageName="):
                info["installer"] = line.split("=", 1)[1]
        return cls(**info)
