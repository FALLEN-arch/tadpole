import subprocess
import unittest
from unittest import mock

from tadpole import adb


def completed(stdout=b"", stderr=b"", code=0):
    return subprocess.CompletedProcess(["adb"], code, stdout, stderr)


class RunTests(unittest.TestCase):
    def setUp(self):
        which = mock.patch("tadpole.adb.shutil.which", return_value="/usr/bin/adb")
        which.start()
        self.addCleanup(which.stop)

    def test_adb_missing_raises_helpful_error(self):
        with mock.patch("tadpole.adb.shutil.which", return_value=None):
            with self.assertRaisesRegex(adb.AdbError, "adb not found"):
                adb.run(None, ["devices"])

    def test_argv_has_serial_and_never_uses_a_shell(self):
        with mock.patch("tadpole.adb.subprocess.run", return_value=completed(b"ok")) as run:
            self.assertEqual(adb.run("S1", ["shell", "ls"]), "ok")
        argv = run.call_args.args[0]
        self.assertEqual(argv, ["/usr/bin/adb", "-s", "S1", "shell", "ls"])
        self.assertNotIn("shell", run.call_args.kwargs)

    def test_no_serial_means_no_dash_s(self):
        with mock.patch("tadpole.adb.subprocess.run", return_value=completed()) as run:
            adb.run(None, ["devices"])
        self.assertEqual(run.call_args.args[0], ["/usr/bin/adb", "devices"])

    def test_error_prefers_stderr(self):
        with mock.patch("tadpole.adb.subprocess.run", return_value=completed(b"out", b"boom", 1)):
            with self.assertRaisesRegex(adb.AdbError, "boom"):
                adb.run("S", ["x"])

    def test_error_falls_back_to_stdout_then_exit_code(self):
        with mock.patch("tadpole.adb.subprocess.run", return_value=completed(b"only stdout", b"", 1)):
            with self.assertRaisesRegex(adb.AdbError, "only stdout"):
                adb.run("S", ["x"])
        with mock.patch("tadpole.adb.subprocess.run", return_value=completed(b"", b"", 7)):
            with self.assertRaisesRegex(adb.AdbError, "code 7"):
                adb.run("S", ["x"])

    def test_run_bytes_returns_raw_and_does_not_use_stdout_in_errors(self):
        with mock.patch("tadpole.adb.subprocess.run", return_value=completed(b"\x89PNG")):
            self.assertEqual(adb.run_bytes("S", ["exec-out", "screencap", "-p"]), b"\x89PNG")
        with mock.patch("tadpole.adb.subprocess.run", return_value=completed(b"\x89PNG", b"", 1)):
            with self.assertRaisesRegex(adb.AdbError, "code 1"):
                adb.run_bytes("S", ["x"])


class DevicesTests(unittest.TestCase):
    OUTPUT = (
        "List of devices attached\n"
        "* daemon started successfully\n"
        "R58M123 device usb:1-2 product:beyond1 model:SM_G973F device:beyond1 transport_id:3\n"
        "192.168.1.5:5555 offline\n"
        "\n"
        "garbage\n"
    )

    def test_parses_devices(self):
        with mock.patch("tadpole.adb.run", return_value=self.OUTPUT):
            devs = adb.devices()
        self.assertEqual([d["serial"] for d in devs], ["R58M123", "192.168.1.5:5555"])
        self.assertEqual(devs[0]["model"], "SM_G973F")
        self.assertEqual(devs[0]["state"], "device")
        self.assertEqual(devs[0]["transport_id"], "3")
        self.assertEqual(devs[1]["model"], "")
        self.assertEqual(devs[1]["state"], "offline")


class SnapshotTests(unittest.TestCase):
    GOOD = (
        "@@P\nPixel 7\ngoogle\n14\n34\narm64-v8a\n"
        "@@B\nAC powered: false\n  level: 87\n  status: 2\n  temperature: 305\n"
        "@@W\nPhysical size: 1080x2400\n"
    )

    def test_parses_single_call_snapshot(self):
        with mock.patch("tadpole.adb.run", return_value=self.GOOD):
            info, bat, size = adb.snapshot("S")
        self.assertEqual((info["model"], info["brand"], info["android"], info["sdk"], info["abi"]),
                         ("Pixel 7", "google", "14", "34", "arm64-v8a"))
        self.assertEqual(bat, {"level": "87%", "status": "Charging", "temperature": "30.5 C"})
        self.assertEqual(size, "1080x2400")

    def test_empty_snapshot_falls_back_to_individual_calls(self):
        calls = []

        def fake_run(serial, args, timeout=60):
            calls.append(args)
            if args[:2] == ["shell", adb._SNAP_CMD]:
                return "@@P\n\n\n\n\n\n@@B\n@@W\n"
            if args[:3] == ["shell", "getprop", "ro.product.model"]:
                return "Fallback\n"
            if args[:3] == ["shell", "dumpsys", "battery"]:
                return "level: 50\nstatus: 3\n"
            if args[:3] == ["shell", "wm", "size"]:
                return "Physical size: 720x1280\n"
            return "\n"

        with mock.patch("tadpole.adb.run", side_effect=fake_run):
            info, bat, size = adb.snapshot("S")
        self.assertEqual(info["model"], "Fallback")
        self.assertEqual(bat["level"], "50%")
        self.assertEqual(bat["status"], "Discharging")
        self.assertEqual(size, "720x1280")
        self.assertGreater(len(calls), 1)

    def test_helpers_swallow_adb_errors(self):
        with mock.patch("tadpole.adb.run", side_effect=adb.AdbError("nope")):
            self.assertEqual(adb.prop("S", "x"), "")
            self.assertEqual(adb.battery("S"), {})
            self.assertEqual(adb.screen_size("S"), "")


if __name__ == "__main__":
    unittest.main()
