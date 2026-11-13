"""Device-related data models."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DeviceState(str, Enum):
    """ADB/Fastboot device connection states."""
    DEVICE = "device"
    FASTBOOT = "fastboot"
    UNAUTHORIZED = "unauthorized"
    OFFLINE = "offline"
    UNKNOWN = "unknown"

    @property
    def is_ready(self) -> bool:
        return self in (DeviceState.DEVICE, DeviceState.FASTBOOT)

    @property
    def is_adb(self) -> bool:
        return self == DeviceState.DEVICE

    @property
    def is_fastboot(self) -> bool:
        return self == DeviceState.FASTBOOT


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    """Detailed device information from ADB."""
    serial: str
    model: str = ""
    brand: str = ""
    android: str = ""
    sdk: str = ""
    abi: str = ""

    @property
    def display_name(self) -> str:
        name = self.model or self.serial
        if self.brand and self.brand not in name:
            name = f"{self.brand} {name}"
        return name


@dataclass(frozen=True, slots=True)
class BatteryInfo:
    """Battery status information."""
    level: str = ""
    status: str = ""
    temperature: str = ""

    @property
    def is_charging(self) -> bool:
        return self.status.lower() == "charging"


@dataclass(frozen=True, slots=True)
class Device:
    """Complete device representation combining connection state and info."""
    serial: str
    state: DeviceState
    model: str = ""
    product: str = ""
    device: str = ""
    transport_id: str = ""
    info: Optional[DeviceInfo] = None
    battery: Optional[BatteryInfo] = None
    screen_size: str = ""

    @property
    def display_name(self) -> str:
        if self.model:
            return f"{self.model}  ·  {self.serial}  ·  {self.state.value}"
        return f"{self.serial}  ·  {self.state.value}"

    @property
    def is_ready(self) -> bool:
        return self.state.is_ready

    @classmethod
    def from_adb_dict(cls, data: dict) -> Device:
        """Create Device from adb devices -l output dict."""
        state = DeviceState(data.get("state", "unknown"))
        return cls(
            serial=data["serial"],
            state=state,
            model=data.get("model", ""),
            product=data.get("product", ""),
            device=data.get("device", ""),
            transport_id=data.get("transport_id", ""),
        )
