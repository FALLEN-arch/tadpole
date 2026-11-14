import unittest

from tadpole.util import NAME_RE, flash_pct, human, parse_terminal


class FlashPctTests(unittest.TestCase):
    def test_sparse_chunks_report_progress_and_remember_totals(self):
        st = {"i": 1, "n": 1}
        pct = flash_pct("Sending sparse 'system' 2/4 (1024 KB)", st)
        self.assertEqual((st["i"], st["n"]), (2, 4))
        self.assertAlmostEqual(pct, 37.5)

    def test_writing_uses_current_chunk(self):
        self.assertAlmostEqual(flash_pct("Writing 'boot'", {"i": 1, "n": 2}), 50.0)

    def test_plain_sending(self):
        self.assertAlmostEqual(flash_pct("Sending 'boot' (100 KB)", {"i": 1, "n": 1}), 50.0)

    def test_finished_is_100(self):
        self.assertEqual(flash_pct("Finished. Total time: 1s", {"i": 1, "n": 1}), 100.0)

    def test_other_lines_are_ignored(self):
        self.assertIsNone(flash_pct("OKAY [  0.1s]", {"i": 1, "n": 1}))


class HumanTests(unittest.TestCase):
    def test_zero_is_dash(self):
        self.assertEqual(human(0), "-")

    def test_units(self):
        self.assertEqual(human(512), "512 B")
        self.assertEqual(human(1536), "1.5 KiB")
        self.assertEqual(human(64 * 1024 * 1024), "64 MiB")
        self.assertEqual(human(3 * 1024 ** 3), "3.0 GiB")


class NameReTests(unittest.TestCase):
    def test_accepts_partition_names(self):
        for name in ("boot", "vendor_boot", "init_boot", "vbmeta_a"):
            self.assertTrue(NAME_RE.fullmatch(name), name)

    def test_rejects_unsafe_names(self):
        for name in ("", "boot img", "../boot", "boot;rm", "a" * 41):
            self.assertIsNone(NAME_RE.fullmatch(name), name)


class ParseTerminalTests(unittest.TestCase):
    def test_uses_gui_mode_and_selected_device(self):
        self.assertEqual(parse_terminal("shell ls", "adb", "ABC"), ("adb", "ABC", ["shell", "ls"]))

    def test_leading_tool_name_overrides_mode(self):
        self.assertEqual(parse_terminal("fastboot getvar all", "adb", "ABC"), ("fb", "ABC", ["getvar", "all"]))
        self.assertEqual(parse_terminal("adb devices", "fb", "ABC")[0], "adb")

    def test_explicit_serial_wins_over_selection(self):
        self.assertEqual(parse_terminal("adb -s XYZ shell id", "adb", "ABC"), ("adb", "XYZ", ["shell", "id"]))

    def test_serial_without_value_is_an_error(self):
        for raw in ("-s", "adb -s", "adb -s XYZ"):
            with self.assertRaises(ValueError, msg=raw):
                parse_terminal(raw, "adb", "ABC")

    def test_global_commands_do_not_get_a_serial(self):
        self.assertEqual(parse_terminal("devices", "adb", "ABC"), ("adb", None, ["devices"]))
        self.assertEqual(parse_terminal("--version", "fb", "ABC"), ("fb", None, ["--version"]))

    def test_version_is_only_global_for_adb(self):
        # fastboot has no `version` subcommand, so it must stay device-scoped
        self.assertEqual(parse_terminal("version", "fb", "ABC")[1], "ABC")

    def test_empty_and_tool_only_lines(self):
        self.assertIsNone(parse_terminal("", "adb", "ABC"))
        self.assertIsNone(parse_terminal("adb", "adb", "ABC"))

    def test_unbalanced_quotes_raise(self):
        with self.assertRaises(ValueError):
            parse_terminal("shell 'oops", "adb", None)

    def test_no_selected_device_gives_no_serial(self):
        self.assertEqual(parse_terminal("shell ls", "adb", None), ("adb", None, ["shell", "ls"]))


if __name__ == "__main__":
    unittest.main()
