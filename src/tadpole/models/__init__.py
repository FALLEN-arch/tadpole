"""Data models for Tadpole."""
from .device import Device, DeviceState, DeviceInfo, BatteryInfo
from .app import AppInfo, AppState
from .file import FileInfo, FileType
from .flash import FlashPreset, FlashOptions
from .partition import Partition, PartitionType
from .fastboot import FastbootVariables

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
]
