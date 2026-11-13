"""Flash-related data models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True, slots=True)
class FlashOptions:
    """Options for flashing an image."""
    partition: str
    image_path: str
    slot: str = "active"  # active, a, b, all
    disable_verity: bool = False
    disable_verification: bool = False

    def to_fastboot_args(self) -> list[str]:
        """Convert to fastboot command line arguments."""
        args: list[str] = []
        if self.slot != "active":
            args.extend(["--slot", self.slot])
        if self.disable_verity:
            args.append("--disable-verity")
        if self.disable_verification:
            args.append("--disable-verification")
        args.extend(["flash", self.partition, self.image_path])
        return args

    @property
    def is_valid(self) -> bool:
        return bool(self.partition and self.image_path)


@dataclass(frozen=True, slots=True)
class FlashPreset:
    """Saved flash configuration preset."""
    name: str
    partition: str = ""
    slot: str = "active"
    image: str = ""
    verity: bool = False
    verification: bool = False

    def to_options(self) -> FlashOptions:
        return FlashOptions(
            partition=self.partition,
            image_path=self.image,
            slot=self.slot,
            disable_verity=self.verity,
            disable_verification=self.verification,
        )

    @classmethod
    def from_options(cls, name: str, options: FlashOptions) -> FlashPreset:
        return cls(
            name=name,
            partition=options.partition,
            slot=options.slot,
            image=options.image_path,
            verity=options.disable_verity,
            verification=options.disable_verification,
        )

    def to_dict(self) -> dict:
        return {
            "partition": self.partition,
            "slot": self.slot,
            "image": self.image,
            "verity": self.verity,
            "verification": self.verification,
        }

    @classmethod
    def from_dict(cls, name: str, data: dict) -> FlashPreset:
        return cls(
            name=name,
            partition=data.get("partition", ""),
            slot=data.get("slot", "active"),
            image=data.get("image", ""),
            verity=data.get("verity", False),
            verification=data.get("verification", False),
        )
