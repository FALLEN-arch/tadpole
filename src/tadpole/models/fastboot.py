"""Fastboot-related data models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True, slots=True)
class FastbootVariables:
    """All fastboot variables from `fastboot getvar all`."""
    variables: dict[str, str] = field(default_factory=dict)
    partitions: list[Partition] = field(default_factory=list)

    @property
    def is_unlocked(self) -> Optional[bool]:
        unlocked = self.variables.get("unlocked")
        if unlocked == "yes":
            return True
        if unlocked == "no":
            return False
        return None

    @property
    def unlocked_text(self) -> str:
        u = self.is_unlocked
        if u is True:
            return "UNLOCKED"
        if u is False:
            return "LOCKED"
        return "state unknown"

    @property
    def slot_count(self) -> int:
        count = self.variables.get("slot-count")
        try:
            return int(count) if count else 0
        except ValueError:
            return 0

    @property
    def current_slot(self) -> str:
        return self.variables.get("current-slot", "unknown")

    @property
    def product(self) -> str:
        return self.variables.get("product", "unknown")

    @property
    def variant(self) -> str:
        return self.variables.get("variant", "unknown")

    @property
    def version(self) -> str:
        return self.variables.get("version", "unknown")

    @property
    def bootloader_version(self) -> str:
        return self.variables.get("version-bootloader", "unknown")

    @property
    def baseband_version(self) -> str:
        return self.variables.get("version-baseband", "unknown")

    @property
    def secure_boot(self) -> str:
        return self.variables.get("secureboot", "unknown")

    @property
    def kernel(self) -> str:
        return self.variables.get("kernel", "unknown")


# Import here to avoid circular dependency
from .partition import Partition
