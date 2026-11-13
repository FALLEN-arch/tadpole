"""Preset service - manages saved flash presets."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..models.flash import FlashPreset


class PresetService:
    """Manages flash presets stored in JSON."""

    def __init__(self, config_dir: Path):
        self._config_dir = config_dir
        self._presets_file = config_dir / "presets.json"
        self._presets: dict[str, FlashPreset] = {}
        self.load()

    def load(self) -> dict[str, FlashPreset]:
        """Load presets from disk."""
        try:
            data = json.loads(self._presets_file.read_text(encoding="utf-8"))
            self._presets = {
                name: FlashPreset.from_dict(name, preset_data)
                for name, preset_data in data.items()
            }
        except Exception:
            self._presets = {}
        return self._presets

    def save(self) -> None:
        """Save presets to disk."""
        try:
            self._config_dir.mkdir(parents=True, exist_ok=True)
            data = {name: preset.to_dict() for name, preset in self._presets.items()}
            self._presets_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def get_all(self) -> dict[str, FlashPreset]:
        """Get all presets."""
        return self._presets.copy()

    def get(self, name: str) -> Optional[FlashPreset]:
        """Get a preset by name."""
        return self._presets.get(name)

    def add(self, preset: FlashPreset) -> None:
        """Add or update a preset."""
        self._presets[preset.name] = preset
        self.save()

    def delete(self, name: str) -> bool:
        """Delete a preset. Returns True if deleted."""
        if name in self._presets:
            del self._presets[name]
            self.save()
            return True
        return False

    def get_names(self) -> list[str]:
        """Get sorted list of preset names."""
        return sorted(self._presets.keys())
