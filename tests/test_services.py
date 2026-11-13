"""Tests for services (mocked)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tadpole.services.adb_service import AdbService, AdbError
from tadpole.services.fastboot_service import FastbootService, FastbootError
from tadpole.services.preset_service import PresetService
from tadpole.services.config_service import ConfigService
from tadpole.models.flash import FlashPreset


def test_adb_service_creation():
    with patch("shutil.which", return_value="/fake/adb"):
        service = AdbService()
        assert service.adb_path == "/fake/adb"


def test_adb_service_missing():
    with patch("shutil.which", return_value=None):
        try:
            AdbService()
            assert False, "Should raise AdbError"
        except AdbError as e:
            assert "adb not found" in str(e)


def test_fastboot_service_creation():
    with patch("shutil.which", return_value="/fake/fastboot"):
        service = FastbootService()
        assert service.fastboot_path == "/fake/fastboot"


def test_fastboot_service_missing():
    with patch("shutil.which", return_value=None):
        try:
            FastbootService()
            assert False, "Should raise FastbootError"
        except FastbootError as e:
            assert "fastboot not found" in str(e)


def test_preset_service(tmp_path):
    service = PresetService(tmp_path)
    assert service.get_all() == {}

    preset = FlashPreset(name="test", partition="boot", image="boot.img")
    service.add(preset)

    assert "test" in service.get_all()
    assert service.get("test").partition == "boot"

    service.delete("test")
    assert "test" not in service.get_all()


def test_preset_service_persistence(tmp_path):
    service1 = PresetService(tmp_path)
    preset = FlashPreset(name="persist", partition="recovery", image="recovery.img")
    service1.add(preset)

    service2 = PresetService(tmp_path)
    assert "persist" in service2.get_all()
    assert service2.get("persist").partition == "recovery"


def test_config_service(tmp_path):
    config = ConfigService(tmp_path)
    assert config.load("test.json", "default") == "default"

    config.save("test.json", "saved_value")
    assert config.load("test.json", "default") == "saved_value"

    config.save("test.json", {"key": "value"})
    assert config.load("test.json", {}) == {"key": "value"}


def test_config_service_validator(tmp_path):
    config = ConfigService(tmp_path)
    config.save("test.json", "not_a_dict")
    # Should return default when type doesn't match
    assert config.load("test.json", {}) == {}


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        test_adb_service_creation()
        test_adb_service_missing()
        test_fastboot_service_creation()
        test_fastboot_service_missing()
        test_preset_service(Path(tmp))
        test_preset_service_persistence(Path(tmp))
        test_config_service(Path(tmp))
        test_config_service_validator(Path(tmp))
    print("All service tests passed!")
