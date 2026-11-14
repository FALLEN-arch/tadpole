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

The installer installs system packages (Python, Tkinter, adb and fastboot), creates a project-local `.venv`, and installs Tadpole's Python dependencies inside it. It supports Debian / Ubuntu, Fedora and Arch package managers. The virtual environment uses system site packages so it can access the distribution's Tkinter module.

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
install.sh         one-step installer; creates .venv
requirements.txt   Python dependencies (tkinterdnd2, for drag and drop)
scripts/run.sh     run using the project virtual environment
src/tadpole/
  gui.py           the Tkinter app
  adb.py           safe wrapper around the adb binary
  fastboot.py      safe wrapper around the fastboot binary
tests/             smoke tests
```

The wrappers build argument lists and never use a local shell for adb / fastboot execution. Remote shell arguments are explicitly quoted where paths are passed to Android's shell.

## License

[MIT](LICENSE) © 2026 fallen-arch
