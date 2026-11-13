"""Config service - manages application configuration."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, TypeVar, Callable

T = TypeVar("T")


class ConfigService:
    """Manages application configuration stored as JSON files."""

    def __init__(self, config_dir: Path):
        self._config_dir = config_dir
        # Migrate from old name if needed
        if not config_dir.exists():
            old = Path.home() / ".adb-studio"
            if old.is_dir():
                # Use the old directory as config dir
                self._config_dir = old

    def _get_file(self, name: str) -> Path:
        return self._config_dir / name

    def load(self, name: str, default: T, validator: Optional[Callable[[Any], T]] = None) -> T:
        """Load JSON config with optional validation."""
        path = self._get_file(name)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if validator:
                return validator(data)
            if isinstance(data, type(default)):
                return data
        except Exception:
            pass
        return default

    def save(self, name: str, data: Any) -> None:
        """Save JSON config."""
        try:
            self._config_dir.mkdir(parents=True, exist_ok=True)
            self._get_file(name).write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def delete(self, name: str) -> bool:
        """Delete a config file."""
        path = self._get_file(name)
        try:
            path.unlink()
            return True
        except OSError:
            return False

    @property
    def config_dir(self) -> Path:
        return self._config_dir
