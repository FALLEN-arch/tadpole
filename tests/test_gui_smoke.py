import importlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import tk_stub


class GuiSmokeTests(unittest.TestCase):
    """Builds the whole window against a fake Tk (no display needed)."""

    def setUp(self):
        ctx = tk_stub.fake_tk()
        ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.conf = Path(tmp.name)
        for target in ("tadpole.config.CONF",):
            p = mock.patch(target, self.conf)
            p.start()
            self.addCleanup(p.stop)
        self.adb = importlib.import_module("tadpole.adb")
        self.fb = importlib.import_module("tadpole.fastboot")
        for target in ("tadpole.adb.devices", "tadpole.fastboot.devices"):
            p = mock.patch(target, return_value=[])
            p.start()
            self.addCleanup(p.stop)
        # never pop real dialogs / spawn real tools
        p = mock.patch("tadpole.deps.missing_tools", return_value=[])
        p.start()
        self.addCleanup(p.stop)
        self.app_mod = importlib.import_module("tadpole.app")

    def test_window_builds_every_tab(self):
        app = self.app_mod.App()
        self.assertEqual(len(app.nb["adb"].tabs), 6)
        self.assertEqual(len(app.nb["fb"].tabs), 5)

    def test_app_composes_both_tab_mixins(self):
        from tadpole.tabs.adb_tabs import AdbTabs
        from tadpole.tabs.fastboot_tabs import FastbootTabs
        self.assertTrue(issubclass(self.app_mod.App, AdbTabs))
        self.assertTrue(issubclass(self.app_mod.App, FastbootTabs))
        for name in ("b_overview", "b_apps", "b_files", "b_shell", "b_logcat", "b_screen", "stop_log",
                     "b_fbdevice", "b_flash", "b_parts", "b_boot", "b_reboot", "load_vars"):
            self.assertTrue(callable(getattr(self.app_mod.App, name)), name)

    def test_switching_mode_and_theme_does_not_crash_and_theme_is_saved(self):
        app = self.app_mod.App()
        app.mode.set("fb")
        app.switch()
        app.apply_theme("light")
        self.assertEqual(app.theme, "light")
        self.assertIn('"light"', (self.conf / "config.json").read_text())
        theme = importlib.import_module("tadpole.theme")
        self.assertEqual(theme.BG, theme.PALETTES["light"]["BG"])
        app.apply_theme("dark")
        self.assertEqual(theme.BG, theme.PALETTES["dark"]["BG"])

    def test_saved_theme_is_loaded_at_start(self):
        (self.conf / "config.json").write_text('{"theme": "light"}')
        app = self.app_mod.App()
        self.assertEqual(app.theme, "light")

    def test_check_tools_warns_once_when_tools_are_missing(self):
        app = self.app_mod.App()
        with mock.patch("tadpole.deps.missing_tools", return_value=["adb"]), \
                mock.patch.object(self.app_mod.messagebox, "showwarning", create=True) as warn, \
                mock.patch.object(app, "log") as log:
            app.check_tools()
        warn.assert_called_once()
        self.assertIn("adb not found", warn.call_args.args[1])
        self.assertEqual(log.call_args.args[0], "setup")

    def test_tool_check_is_scheduled_at_startup(self):
        scheduled = []
        with mock.patch.object(tk_stub.Widget, "after", create=True,
                               new=lambda self, ms, fn=None, *a: scheduled.append((ms, getattr(fn, "__name__", "")))):
            self.app_mod.App()
        self.assertIn((300, "check_tools"), scheduled)

    def test_check_tools_is_silent_when_everything_is_installed(self):
        app = self.app_mod.App()
        with mock.patch.object(self.app_mod.messagebox, "showwarning", create=True) as warn:
            app.check_tools()
        warn.assert_not_called()

    def test_run_cmd_dispatches_with_explicit_serial(self):
        app = self.app_mod.App()
        app.cmd.get = lambda: "adb -s XYZ shell id"
        with mock.patch.object(self.app_mod.adb, "run", return_value="uid=2000") as run, \
                mock.patch.object(app, "bg") as bg:
            app.run_cmd(None)
            self.assertEqual(bg.call_args.args[2], "adb -s XYZ shell id")
            self.assertEqual(bg.call_args.args[0](), "uid=2000")
        run.assert_called_once_with("XYZ", ["shell", "id"], 120)

    def test_run_cmd_reports_bad_serial_instead_of_running(self):
        app = self.app_mod.App()
        app.cmd.get = lambda: "adb -s"
        with mock.patch.object(app, "bg") as bg, mock.patch.object(app, "log") as log:
            app.run_cmd(None)
        bg.assert_not_called()
        self.assertIn("serial", log.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
