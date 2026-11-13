"""Partition-related data models."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PartitionType(Enum):
    """Partition type."""
    PHYSICAL = "physical"
    LOGICAL = "logical"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Partition:
    """Partition information from fastboot."""
    name: str
    size: int = 0
    type: PartitionType = PartitionType.UNKNOWN
    logical: bool = False

    def __post_init__(self):
        # Auto-set type from logical if not explicitly provided
        if self.type == PartitionType.UNKNOWN:
            object.__setattr__(self, 'type', PartitionType.LOGICAL if self.logical else PartitionType.PHYSICAL)

    @property
    def base_name(self) -> str:
        """Partition name without slot suffix (_a, _b)."""
        if self.name.endswith(("_a", "_b")):
            return self.name[:-2]
        return self.name

    @property
    def slot_suffix(self) -> str:
        """Slot suffix if present (_a, _b)."""
        if self.name.endswith("_a"):
            return "_a"
        if self.name.endswith("_b"):
            return "_b"
        return ""

    def human_size(self) -> str:
        """Human-readable size."""
        if not self.size:
            return "-"
        size = self.size
        for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
            if size < 1024 or unit == "TiB":
                return f"{size:.0f} {unit}" if size >= 10 or unit == "B" else f"{size:.1f} {unit}"
            size /= 1024
        return "-"

    @classmethod
    def from_fastboot_dict(cls, data: dict) -> Partition:
        """Create Partition from fastboot getvar output dict."""
        name = data.get("name", "")
        size = data.get("size", 0)
        logical = data.get("logical", False)
        return cls(
            name=name,
            size=size,
            logical=logical,
        )
