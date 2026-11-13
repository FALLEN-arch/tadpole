"""File-related data models."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class FileType(Enum):
    """File system entry type."""
    FILE = "file"
    DIRECTORY = "directory"
    SYMLINK = "symlink"
    UNKNOWN = "unknown"

    @classmethod
    def from_ls_output(cls, name: str, is_dir: bool) -> FileType:
        if is_dir:
            return cls.DIRECTORY
        return cls.FILE


@dataclass(frozen=True, slots=True)
class FileInfo:
    """File system entry information."""
    name: str
    path: str
    type: FileType
    size: int = 0
    permissions: str = ""
    owner: str = ""
    modified: str = ""
    is_hidden: bool = False

    @property
    def is_dir(self) -> bool:
        return self.type == FileType.DIRECTORY

    @property
    def is_file(self) -> bool:
        return self.type == FileType.FILE

    @classmethod
    def from_ls_line(cls, line: str, base_path: str) -> Optional[FileInfo]:
        """Parse a line from `ls -la` output."""
        # Format: -rw-r--r-- 1 user group size date time name
        parts = line.split(maxsplit=7)
        if len(parts) < 8:
            return None
        perms, _, owner, _, size_str, *date_parts, name = parts
        try:
            size = int(size_str)
        except ValueError:
            size = 0

        ftype = FileType.FILE
        if perms.startswith("d"):
            ftype = FileType.DIRECTORY
        elif perms.startswith("l"):
            ftype = FileType.SYMLINK

        full_path = base_path.rstrip("/") + "/" + name
        return cls(
            name=name,
            path=full_path,
            type=ftype,
            size=size,
            permissions=perms,
            owner=owner,
            modified=" ".join(date_parts),
            is_hidden=name.startswith("."),
        )
