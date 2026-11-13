"""UI layer for Tadpole - widgets, tabs, and main application."""
from .widgets import (
    make_text_widget,
    make_tree_widget,
    SideNav,
    Toolbar,
    StatusPill,
    confirm_dialog,
)
from .tabs import (
    TabBase,
    AdbOverviewTab,
    AdbAppsTab,
    AdbFilesTab,
    AdbShellTab,
    AdbLogcatTab,
    AdbScreenTab,
    FastbootDeviceTab,
    FastbootFlashTab,
    FastbootPartitionsTab,
    FastbootBootloaderTab,
    FastbootRebootTab,
)
from .main_window import MainWindow

__all__ = [
    "make_text_widget",
    "make_tree_widget",
    "SideNav",
    "Toolbar",
    "StatusPill",
    "confirm_dialog",
    "TabBase",
    "AdbOverviewTab",
    "AdbAppsTab",
    "AdbFilesTab",
    "AdbShellTab",
    "AdbLogcatTab",
    "AdbScreenTab",
    "FastbootDeviceTab",
    "FastbootFlashTab",
    "FastbootPartitionsTab",
    "FastbootBootloaderTab",
    "FastbootRebootTab",
    "MainWindow",
]
