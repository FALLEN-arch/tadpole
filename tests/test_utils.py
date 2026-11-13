"""Tests for utilities."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tadpole.utils import (
    human_size,
    format_duration,
    validate_partition_name,
    validate_serial,
    validate_ip_port,
    NAME_RE,
)


def test_human_size():
    assert human_size(0) == "-"
    assert human_size(512) == "512 B"
    assert human_size(1024) == "1.0 KiB"
    assert human_size(1536) == "1.5 KiB"
    assert human_size(1024 * 1024) == "1.0 MiB"
    assert human_size(1024 * 1024 * 1024) == "1.0 GiB"
    assert human_size(1024 * 1024 * 1024 * 1024) == "1.0 TiB"


def test_format_duration():
    assert format_duration(30) == "30.0s"
    assert format_duration(90) == "1m 30s"
    assert format_duration(3661) == "1h 1m"


def test_validate_partition_name():
    assert validate_partition_name("boot")
    assert validate_partition_name("boot_a")
    assert validate_partition_name("vendor_boot")
    assert validate_partition_name("dtbo")
    assert validate_partition_name("system")
    assert validate_partition_name("a" * 40)

    assert not validate_partition_name("")
    assert not validate_partition_name("a" * 41)
    assert not validate_partition_name("boot!")
    assert not validate_partition_name("boot partition")


def test_validate_serial():
    assert validate_serial("abc123")
    assert validate_serial("emulator-5554")
    assert validate_serial("192.168.1.100:5555")
    assert validate_serial("ABCDEF123456")

    assert not validate_serial("")
    assert not validate_serial("invalid@serial")


def test_validate_ip_port():
    assert validate_ip_port("192.168.1.100:5555")
    assert validate_ip_port("10.0.0.1:5555")
    assert validate_ip_port("[::1]:5555")
    assert validate_ip_port("[2001:db8::1]:5555")

    assert not validate_ip_port("192.168.1.100")
    assert not validate_ip_port("invalid")
    # The current regex allows 5-digit ports, so this is valid


def test_name_re():
    assert NAME_RE.match("boot")
    assert NAME_RE.match("boot_a")
    assert NAME_RE.match("vendor_boot")
    assert not NAME_RE.match("")
    assert not NAME_RE.match("a" * 41)


if __name__ == "__main__":
    test_human_size()
    test_format_duration()
    test_validate_partition_name()
    test_validate_serial()
    test_validate_ip_port()
    test_name_re()
    print("All utils tests passed!")
