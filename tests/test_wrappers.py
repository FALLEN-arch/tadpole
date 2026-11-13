import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tadpole import adb, fastboot  # noqa: E402


def test_modules_expose_errors():
    assert issubclass(adb.AdbError, RuntimeError)
    assert issubclass(fastboot.FastbootError, RuntimeError)
