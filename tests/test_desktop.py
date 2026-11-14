import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tadpole import desktop, gui


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict(os.environ, {"XDG_DATA_HOME": self.tmp.name})
        env.start()
        self.addCleanup(env.stop)

    def test_install_writes_entry_and_icon(self):
        files = desktop.install()
        entry, icon = desktop.paths()
        self.assertEqual(files, [entry, icon])
        self.assertTrue(icon.is_file())
        self.assertEqual(icon.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        text = entry.read_text(encoding="utf-8")
        self.assertIn("Icon=tadpole", text)
        self.assertIn("StartupWMClass=Tadpole", text)
        self.assertIn("Exec=", text)
        self.assertTrue(str(entry).startswith(self.tmp.name))

    def test_install_twice_is_fine_and_uninstall_removes_both(self):
        desktop.install()
        desktop.install()
        removed = desktop.uninstall()
        self.assertEqual(len(removed), 2)
        self.assertFalse(any(p.exists() for p in desktop.paths()))
        self.assertEqual(desktop.uninstall(), [])

    def test_launch_command_prefers_script_next_to_python(self):
        script = Path(self.tmp.name) / "bin" / "tadpole"
        script.parent.mkdir()
        script.write_text("#!/bin/sh\n")
        with mock.patch("tadpole.desktop.sys.executable", str(script.parent / "python")):
            self.assertEqual(desktop.launch_command(), f'"{script}"')

    def test_launch_command_falls_back_to_module(self):
        with mock.patch("tadpole.desktop.sys.executable", "/nonexistent/python"):
            self.assertEqual(desktop.launch_command(), '"/nonexistent/python" -m tadpole')

    def test_bundled_icons_exist(self):
        for size in (256, 64):
            self.assertTrue((desktop.ASSETS / f"tadpole-{size}.png").is_file())


class CliTests(unittest.TestCase):
    def setUp(self):
        out = contextlib.redirect_stdout(io.StringIO())
        out.__enter__()
        self.addCleanup(out.__exit__, None, None, None)

    def test_install_and_uninstall_desktop_flags(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"XDG_DATA_HOME": tmp}):
            gui.main(["--install-desktop"])
            self.assertTrue(all(p.exists() for p in desktop.paths()))
            gui.main(["--uninstall-desktop"])
            self.assertFalse(any(p.exists() for p in desktop.paths()))

    def test_check_exit_code_reflects_problems(self):
        with mock.patch("tadpole.deps.python_problems", return_value=[]), \
                mock.patch("tadpole.deps.missing_tools", return_value=[]):
            with self.assertRaises(SystemExit) as ctx:
                gui.main(["--check"])
            self.assertEqual(ctx.exception.code, 0)
        with mock.patch("tadpole.deps.python_problems", return_value=[]), \
                mock.patch("tadpole.deps.missing_tools", return_value=["adb"]):
            with self.assertRaises(SystemExit) as ctx:
                gui.main(["--check"])
            self.assertEqual(ctx.exception.code, 1)

    def test_start_aborts_cleanly_when_python_modules_are_missing(self):
        with mock.patch("tadpole.deps.python_problems", return_value=["Tkinter is missing."]), \
                mock.patch("tadpole.deps.missing_tools", return_value=[]):
            with self.assertRaisesRegex(SystemExit, "Tkinter is missing"):
                gui.main([])


if __name__ == "__main__":
    unittest.main()
