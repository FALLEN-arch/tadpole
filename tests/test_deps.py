import unittest

from tadpole import deps

DEBIAN = 'ID=ubuntu\nID_LIKE="debian"\n'
FEDORA = "ID=fedora\n"
ARCH = "ID=endeavouros\nID_LIKE=arch\n"
SUSE = 'ID="opensuse-tumbleweed"\nID_LIKE="opensuse suse"\n'
UNKNOWN = "ID=plan9\n"


class ToolTests(unittest.TestCase):
    def test_missing_tools_reports_only_absent_ones(self):
        self.assertEqual(deps.missing_tools(which=lambda t: "/bin/" + t), [])
        self.assertEqual(deps.missing_tools(which=lambda t: None), ["adb", "fastboot"])
        self.assertEqual(deps.missing_tools(which=lambda t: "/bin/adb" if t == "adb" else None), ["fastboot"])

    def test_install_hint_per_distro(self):
        self.assertIn("apt install adb fastboot", deps.install_hint(DEBIAN))
        self.assertIn("dnf install android-tools", deps.install_hint(FEDORA))
        self.assertIn("pacman -S android-tools", deps.install_hint(ARCH))
        self.assertIn("zypper install android-tools", deps.install_hint(SUSE))
        self.assertIn("platform-tools", deps.install_hint(UNKNOWN))

    def test_message_names_missing_tool_and_affected_mode(self):
        msg = deps.tools_message(["fastboot"], DEBIAN)
        self.assertIn("fastboot not found", msg)
        self.assertIn("Fastboot mode", msg)
        self.assertNotIn("ADB mode", msg)
        both = deps.tools_message(["adb", "fastboot"], DEBIAN)
        self.assertIn("adb and fastboot", both)
        self.assertIn("ADB mode, Fastboot mode", both)


class PythonProblemTests(unittest.TestCase):
    def test_all_present(self):
        self.assertEqual(deps.python_problems(find_spec=lambda name: object()), [])

    def test_reports_each_missing_module(self):
        msgs = deps.python_problems(find_spec=lambda name: None)
        self.assertEqual(len(msgs), 2)
        self.assertIn("Tkinter", msgs[0])
        self.assertIn("pip install tkinterdnd2", msgs[1])

    def test_only_dnd_missing(self):
        msgs = deps.python_problems(find_spec=lambda name: None if name == "tkinterdnd2" else object())
        self.assertEqual(len(msgs), 1)
        self.assertIn("drag and drop", msgs[0])


if __name__ == "__main__":
    unittest.main()
