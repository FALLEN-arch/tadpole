"""Tests for data models."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tadpole.models import (
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


def test_device_state():
    assert DeviceState.DEVICE.is_ready
    assert DeviceState.FASTBOOT.is_ready
    assert not DeviceState.UNAUTHORIZED.is_ready
    assert DeviceState.DEVICE.is_adb
    assert DeviceState.FASTBOOT.is_fastboot


def test_device_info_display_name():
    info = DeviceInfo(serial="123", model="Pixel 8", brand="Google")
    assert info.display_name == "Google Pixel 8"

    info2 = DeviceInfo(serial="123", model="Pixel 8")
    assert info2.display_name == "Pixel 8"


def test_device_from_adb_dict():
    data = {
        "serial": "abc123",
        "state": "device",
        "model": "Pixel 8",
        "product": "pixel8",
        "device": "pixel8",
        "transport_id": "1",
    }
    device = Device.from_adb_dict(data)
    assert device.serial == "abc123"
    assert device.state == DeviceState.DEVICE
    assert device.model == "Pixel 8"
    assert device.is_ready


def test_app_info():
    app = AppInfo(package="com.test", name="Test App", version="1.0", state=AppState.ENABLED)
    assert app.display_name == "Test App"
    assert app.is_enabled

    app2 = AppInfo(package="com.test")
    assert app2.display_name == "com.test"
    assert not app2.is_enabled


def test_file_info():
    file = FileInfo(name="test.txt", path="/sdcard/test.txt", type=FileType.FILE, size=1024)
    assert file.is_file
    assert not file.is_dir

    dir_info = FileInfo(name="folder", path="/sdcard/folder", type=FileType.DIRECTORY)
    assert dir_info.is_dir
    assert not dir_info.is_file


def test_flash_options():
    opts = FlashOptions(partition="boot", image_path="/path/to/boot.img", slot="a")
    args = opts.to_fastboot_args()
    assert "--slot" in args
    assert "a" in args
    assert "flash" in args
    assert "boot" in args
    assert "/path/to/boot.img" in args
    assert opts.is_valid


def test_flash_preset():
    preset = FlashPreset(name="test", partition="boot", slot="a", image="boot.img", verity=True)
    opts = preset.to_options()
    assert opts.partition == "boot"
    assert opts.slot == "a"
    assert opts.disable_verity

    data = preset.to_dict()
    assert data["partition"] == "boot"
    assert data["verity"] is True

    preset2 = FlashPreset.from_dict("test", data)
    assert preset2.name == "test"
    assert preset2.verity is True


def test_partition():
    p = Partition(name="boot_a", size=1024 * 1024 * 64, logical=False)
    assert p.base_name == "boot"
    assert p.slot_suffix == "_a"
    assert p.type == PartitionType.PHYSICAL
    assert "MiB" in p.human_size()

    p2 = Partition(name="system", size=0, logical=True)
    assert p2.type == PartitionType.LOGICAL


def test_fastboot_variables():
    vars = FastbootVariables(
        variables={"unlocked": "yes", "product": "pixel8", "current-slot": "a"},
        partitions=[Partition(name="boot_a", size=1024, logical=False)],
    )
    assert vars.is_unlocked is True
    assert vars.unlocked_text == "UNLOCKED"
    assert vars.current_slot == "a"
    assert vars.product == "pixel8"
    assert vars.slot_count == 0  # not set

    vars2 = FastbootVariables(variables={"unlocked": "no"})
    assert vars2.is_unlocked is False
    assert vars2.unlocked_text == "LOCKED"

    vars3 = FastbootVariables(variables={})
    assert vars3.is_unlocked is None
    assert vars3.unlocked_text == "state unknown"


if __name__ == "__main__":
    test_device_state()
    test_device_info_display_name()
    test_device_from_adb_dict()
    test_app_info()
    test_file_info()
    test_flash_options()
    test_flash_preset()
    test_partition()
    test_fastboot_variables()
    print("All model tests passed!")
