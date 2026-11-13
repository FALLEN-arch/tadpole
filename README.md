# 🐸 Tadpole

A native Linux desktop GUI for **adb** and **fastboot**. Built on Tkinter: no web server, no browser, no Electron.

![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![Platform: Linux](https://img.shields.io/badge/platform-Linux-lightgrey)

## Features

**ADB**
- Device overview and wireless connect / pair
- Apps: launch, stop, clear data, uninstall, disable / enable, pull APK, install APK
- File browser: pull, push, delete
- Shell and logcat (level filter, find box, save to file)
- Screen tab: live view, click the screenshot to tap, Back / Home / Recents / Power / Volume keys
- Screenshots, `adb root`, ZIP sideload

**Fastboot**
- Read variables, list partitions
- Flash with slot selection and disable-verity / disable-verification, with a progress bar
- Saved flash presets
- Unlock / lock, wipe, erase, set active slot
- Reboot to system, bootloader, recovery or fastbootd

**Everywhere**
- Drag and drop: drop `.apk` files to install (ADB mode) or an `.img` to prepare a flash (Fastboot mode)
- Terminal dock that runs any adb or fastboot command, with history (Up / Down) and Clear
- Dark theme (Sun Valley, via sv-ttk)
- Destructive actions need a typed confirmation (`FLASH`, `ERASE`, `UNLOCK`, `LOCK`, `WIPE`)

## Install

```bash
git clone https://github.com/FALLEN-arch/tadpole.git
cd tadpole
./install.sh
```

The installer sets up everything in one go: Python, Tkinter, `adb`, `fastboot`, `pipx`, and Tadpole itself
with its Python dependencies: `tkinterdnd2` (drag and drop), `sv-ttk` (the dark Sun Valley theme) and `Pillow` (screen view scaling). It supports Debian / Ubuntu, Fedora and Arch.

<details>
<summary>Manual install</summary>

```bash
sudo apt install python3 python3-tk pipx adb fastboot
pipx install --system-site-packages .
```

`pipx` also installs the Python dependencies (`tkinterdnd2`, `sv-ttk`, `Pillow`) automatically. `--system-site-packages` lets pipx's isolated environment see the system Tkinter.

</details>

## Usage

```bash
tadpole
```

If `tadpole` isn't found, open a new terminal or run `export PATH="$HOME/.local/bin:$PATH"`.

You can also run straight from a checkout without installing. Install the Python dependencies first
(`tkinterdnd2`, `sv-ttk` and `Pillow`):

```bash
pip install -r requirements.txt
./scripts/run.sh
```

## Development

```bash
# Run tests
python3 -m pytest tests/ -v

# Run from source (requires dependencies)
pip install -r requirements.txt
python3 -m tadpole
```

## Configuration

Saved flash presets are stored in `~/.tadpole/`. An existing `~/.adb-studio/` folder from the
old name is still picked up automatically.

## Project Layout

```
install.sh            one-step installer
requirements.txt      Python dependencies (tkinterdnd2, sv-ttk, Pillow)
scripts/run.sh        run from a checkout
tests/                unit tests
src/tadpole/
  __init__.py         package exports (models, services, errors)
  __main__.py         entry point
  models/             data models (dataclasses, enums)
    device.py         Device, DeviceState, DeviceInfo, BatteryInfo
    app.py            AppInfo, AppState
    file.py           FileInfo, FileType
    flash.py          FlashOptions, FlashPreset
    partition.py      Partition, PartitionType
    fastboot.py       FastbootVariables
  services/           business logic (stateless, serial-targeted)
    adb_service.py    AdbService - all ADB operations
    fastboot_service.py  FastbootService - all fastboot operations
    preset_service.py    PresetService - flash presets persistence
    config_service.py    ConfigService - JSON config management
  ui/                 UI layer (Tkinter)
    widgets.py        reusable widgets (SideNav, Toolbar, StatusPill, etc.)
    tabs.py           12 tab classes (6 ADB + 6 Fastboot)
    main_window.py    MainWindow - orchestrates everything
  utils/              shared utilities
    threading.py      background task queue with UI callbacks
    formatting.py     human_size, format_duration
    validation.py     input validation regexes
    theme.py          dark theme constants & styling helpers
```

The wrappers build argument lists and never use a shell, so serials, package names and paths can't be
interpreted as shell syntax.

## Architecture

Tadpole follows a clean **modular architecture**:

| Layer | Responsibility |
|-------|----------------|
| **Models** | Frozen dataclasses + enums for type-safe data |
| **Services** | Stateless business logic (ADB, fastboot, presets, config) |
| **UI** | Tkinter widgets, tabs, and main window orchestration |
| **Utils** | Threading, formatting, validation, theming |

All background operations run on a thread pool with results delivered to the UI thread via a queue, keeping the interface responsive.

## License

[MIT](LICENSE) © 2026 fallen-arch
