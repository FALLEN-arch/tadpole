"""Settings storage in ~/.tadpole (theme, flash presets)."""
from __future__ import annotations

import json
from pathlib import Path

CONF = Path.home() / ".tadpole"
if not CONF.exists() and (Path.home() / ".adb-studio").is_dir():
    CONF = Path.home() / ".adb-studio"  # settings from before the rename


def load_json(name, default):
    try:
        data = json.loads((CONF / name).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default
    return data if isinstance(data, type(default)) else default


def save_json(name, data):
    try:
        CONF.mkdir(parents=True, exist_ok=True)
        (CONF / name).write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass
