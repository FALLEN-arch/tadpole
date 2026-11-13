"""Tadpole - Native desktop GUI for adb and fastboot."""
from __future__ import annotations

__version__ = "1.0.0"
__author__ = "fallen-arch"
__license__ = "MIT"

# Re-export key components
from .models import (
    Device,
    DeviceState,
    DeviceInfo,
    BatteryInfo,
    AppInfo,
    AppState,
    FileInfo,
    FileType,
    FlashPreset,
    FlashOptions,
    Partition,
    PartitionType,
    FastbootVariables,
)
from .services import (
    AdbService,
    AdbError,
    FastbootService,
    FastbootError,
    PresetService,
    ConfigService,
)

__all__ = [
    "Device",
    "DeviceState",
    "DeviceInfo",
    "BatteryInfo",
    "AppInfo",
    "AppState",
    "FileInfo",
    "FileType",
    "FlashPreset",
    "FlashOptions",
    "Partition",
    "PartitionType",
    "FastbootVariables",
    "AdbService",
    "AdbError",
    "FastbootService",
    "FastbootError",
    "PresetService",
    "ConfigService",
]
