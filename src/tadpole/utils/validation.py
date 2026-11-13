"""Validation utilities."""
from __future__ import annotations

import re


# Partition name regex: alphanumeric, underscore, hyphen, 1-40 chars
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def validate_partition_name(name: str) -> bool:
    """Validate a partition name."""
    return bool(NAME_RE.match(name))


def validate_serial(serial: str) -> bool:
    """Validate a device serial (basic check)."""
    if not serial:
        return False
    # Serials can contain alphanumeric, dots, colons, hyphens
    return bool(re.match(r"^[A-Za-z0-9.:_-]+$", serial))


def validate_ip_port(address: str) -> bool:
    """Validate an IP:port address."""
    pattern = re.compile(
        r"^((\d{1,3}\.){3}\d{1,3}|\[?[A-Fa-f0-9:]+\]?):\d{1,5}$"
    )
    return bool(pattern.match(address))
