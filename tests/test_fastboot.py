import io
import subprocess
import time
import unittest
from unittest import mock

from tadpole import fastboot as fb


def completed(stdout=b"", stderr=b"", code=0):
    return subprocess.CompletedProcess(["fastboot"], code, stdout, stderr)


class RunTests(unittest.TestCase):
    def setUp(self):
        which = mock.patch("tadpole.fastboot.shutil.which", return_value="/usr/bin/fastboot")
        which.start()
        self.addCleanup(which.stop)

    def test_missing_binary(self):
        with mock.patch("tadpole.fastboot.shutil.which", return_value=None):
            with self.assertRaisesRegex(fb.FastbootError, "fastboot not found"):
                fb.run(None, ["devices"])

    def test_output_combines_stdout_and_stderr(self):
        with mock.patch("tadpole.fastboot.subprocess.run", return_value=completed(b"a\n", b"b\n")) as run:
            self.assertEqual(fb.run("S", ["getvar", "all"]), "a\nb")
        self.assertEqual(run.call_args.args[0], ["/usr/bin/fastboot", "-s", "S", "getvar", "all"])

    def test_failure_raises_with_output_or_code(self):
        with mock.patch("tadpole.fastboot.subprocess.run", return_value=completed(b"", b"FAILED (remote: no)", 1)):
            with self.assertRaisesRegex(fb.FastbootError, "remote: no"):
                fb.run("S", ["flash", "boot", "x"])
        with mock.patch("tadpole.fastboot.subprocess.run", return_value=completed(b"", b"", 9)):
            with self.assertRaisesRegex(fb.FastbootError, "code 9"):
                fb.run("S", ["x"])

    def test_version_handles_empty_output(self):
        with mock.patch("tadpole.fastboot.run", return_value=""):
            self.assertEqual(fb.version(), "Fastboot version unavailable")
        with mock.patch("tadpole.fastboot.run", return_value="fastboot version 35.0.1\nInstalled as /x"):
            self.assertEqual(fb.version(), "fastboot version 35.0.1")


class DevicesTests(unittest.TestCase):
    def test_skips_waiting_and_permission_noise(self):
        out = ("< waiting for any device >\n"
               "no permissions (user in plugdev group; are your udev rules wrong?); see [x]\n"
               "ABC123\tfastboot\n")
        with mock.patch("tadpole.fastboot.run", return_value=out):
            self.assertEqual(fb.devices(), [{"serial": "ABC123", "state": "fastboot"}])


class GetvarTests(unittest.TestCase):
    def test_parses_variables_and_partitions(self):
        out = (
            "(bootloader) version-bootloader: abc\n"
            "(bootloader) unlocked: yes\n"
            "(bootloader) partition-size:boot_a: 0x4000000\n"
            "(bootloader) partition-size:system_a: 0x80000000\n"
            "(bootloader) is-logical:system_a: yes\n"
            "(bootloader) is-logical:boot_a: no\n"
            "(bootloader) partition-size:bad: nothex\n"
            "all: \n"
            "Finished. Total time: 0.01s\n"
        )
        with mock.patch("tadpole.fastboot.run", return_value=out):
            info = fb.getvar_all("S")
        self.assertEqual(info["vars"]["unlocked"], "yes")
        self.assertNotIn("all", info["vars"])
        parts = {p["name"]: p for p in info["partitions"]}
        self.assertEqual(parts["boot_a"]["size"], 0x4000000)
        self.assertFalse(parts["boot_a"]["logical"])
        self.assertTrue(parts["system_a"]["logical"])
        self.assertEqual(parts["bad"]["size"], 0)
        self.assertEqual([p["name"] for p in info["partitions"]], sorted(parts))


class FakePopen:
    def __init__(self, data=b"", code=0, block=False):
        self.stdout = io.BytesIO(data)
        self.returncode = code
        self._block = block
        self.killed = False

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True


class RunStreamTests(unittest.TestCase):
    def setUp(self):
        which = mock.patch("tadpole.fastboot.shutil.which", return_value="/usr/bin/fastboot")
        which.start()
        self.addCleanup(which.stop)

    def test_streams_each_line_and_returns_output(self):
        fake = FakePopen(b"Sending 'boot' (1 KB)\nWriting 'boot'\nFinished.\n")
        seen = []
        with mock.patch("tadpole.fastboot.subprocess.Popen", return_value=fake):
            out = fb.run_stream("S", ["flash", "boot", "x.img"], seen.append, timeout=5)
        self.assertEqual(seen, ["Sending 'boot' (1 KB)", "Writing 'boot'", "Finished."])
        self.assertEqual(out, "\n".join(seen))

    def test_nonzero_exit_raises(self):
        fake = FakePopen(b"FAILED (remote: bad)\n", code=1)
        with mock.patch("tadpole.fastboot.subprocess.Popen", return_value=fake):
            with self.assertRaisesRegex(fb.FastbootError, "remote: bad"):
                fb.run_stream("S", ["flash"], lambda line: None)

    def test_timeout_kills_process(self):
        class Hanging(FakePopen):
            def __init__(self):
                super().__init__()
                self.returncode = None

                class Pipe:
                    def __init__(inner, owner):
                        inner.owner = owner

                    def readline(inner):
                        # block until killed, like a hung fastboot
                        while not inner.owner.killed:
                            time.sleep(0.01)
                        return b""
                self.stdout = Pipe(self)

            def wait(self, timeout=None):
                self.returncode = -9
                return self.returncode

            def poll(self):
                return self.returncode

        fake = Hanging()
        with mock.patch("tadpole.fastboot.subprocess.Popen", return_value=fake):
            with self.assertRaisesRegex(fb.FastbootError, "timed out"):
                fb.run_stream("S", ["flash"], lambda line: None, timeout=0.1)
        self.assertTrue(fake.killed)


if __name__ == "__main__":
    unittest.main()
