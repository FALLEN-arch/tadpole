# 🐸 Tadpole

A native Linux desktop GUI for **adb** and **fastboot**. Built on Tkinter: no web server, no browser, no Electron.

![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
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
- Terminal dock that runs adb or fastboot commands, with history (Up / Down) and Clear
- Light / dark theme, remembered between runs
- Destructive actions need a typed confirmation (`FLASH`, `ERASE`, `UNLOCK`, `LOCK`, `WIPE`)

## Install

```bash
git clone https://github.com/FALLEN-arch/tadpole.git
cd tadpole
./install.sh
```

The installer installs system packages (Python, Tkinter, adb and fastboot), creates a project-local `.venv`, installs Tadpole's Python dependencies inside it, and adds Tadpole (with its icon) to your application menu. It supports Debian / Ubuntu, Fedora, Arch and openSUSE package managers. The virtual environment uses system site packages so it can access the distribution's Tkinter module.

| Command | What it does |
| --- | --- |
| `./install.sh` | Full install |
| `./install.sh --no-system` | Skip system packages. Use this without root or sudo (install Python 3.10+, Tkinter, venv support, adb and fastboot yourself first) |
| `./install.sh --uninstall` | Remove the menu entry, icon and `.venv`. Settings in `~/.tadpole` are kept |

Without root or sudo the installer skips the system packages on its own instead of stopping.


## Usage

```bash
./scripts/run.sh
```

Alternatively, activate the environment and use the installed command:

```bash
source .venv/bin/activate
tadpole
```

You can also run from a checkout manually:

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -e .
./scripts/run.sh
```

Useful flags (they work with `scripts/run.sh`, `python -m tadpole` and the `tadpole` command):

```bash
tadpole --check              # report missing Tk, tkinterdnd2, adb or fastboot, then exit (0 = all good)
tadpole --install-desktop    # add the application-menu entry and icon for the current user
tadpole --uninstall-desktop  # remove them again
tadpole --version
```

On start, Tadpole also warns inside the app if `adb` or `fastboot` are not on your `PATH`, with an install command for your distribution.

### USB permissions

If your phone does not show up over USB (or `fastboot devices` prints "no permissions"), your user probably lacks udev rules for it. Install your distribution's rules package, replug the phone and press Refresh:

- Debian / Ubuntu: `android-sdk-platform-tools-common` (the installer tries to add it)
- Arch: `android-udev`
- Others: add the rule for your phone's vendor, see the [Android docs](https://developer.android.com/studio/run/device#setting-up)

### Termux / proot

Install the required Python, Tkinter, venv and Android platform-tools packages for your distribution, then run `./install.sh`. Start Termux:X11 first and point the app at it:

```bash
export DISPLAY=:0
./scripts/run.sh
```

Android blocks USB access from proot, so on a phone use wireless debugging (adb only):

```bash
adb connect 127.0.0.1:5555
```

## Configuration

Presets and the theme choice are stored in `~/.tadpole/`. An existing `~/.adb-studio/` folder from the old name is still picked up automatically.

## Project layout

```
install.sh         installer / uninstaller; creates .venv and the menu entry
requirements.txt   Python dependencies (tkinterdnd2, for drag and drop)
scripts/run.sh     run using the project virtual environment
src/tadpole/
  gui.py           command-line entry point and flags (imports no Tk)
  app.py           main window: top bar, terminal dock, device polling
  tabs/            one mixin per mode: adb_tabs.py, fastboot_tabs.py
  widgets.py       shared Tk widgets (themed text box, tree, sidebar)
  theme.py         light / dark palettes
  config.py        settings in ~/.tadpole
  util.py          pure helpers (flash progress, terminal parsing)
  deps.py          startup checks for Tk, tkinterdnd2, adb, fastboot
  desktop.py       application-menu entry and icon install
  adb.py           safe wrapper around the adb binary
  fastboot.py      safe wrapper around the fastboot binary
  assets/          app icon (window + launcher)
tests/             unit tests plus a no-display GUI smoke test
```

## Development

```bash
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest          # or: python3 -m unittest discover -s tests -t .
```

The tests mock `subprocess`, so no phone, adb or display is needed. The GUI smoke test builds the whole window against a fake Tk (`tests/tk_stub.py`); it catches wiring mistakes but does not render anything, so still try the real app after UI changes.

The wrappers build argument lists and never use a local shell for adb / fastboot execution. Remote shell arguments are explicitly quoted where paths are passed to Android's shell.

## License

[MIT](LICENSE) © 2026 fallen-arch
