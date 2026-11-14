#!/usr/bin/env bash
# Install Tadpole: system packages (optional), a project-local virtual environment,
# and an application-menu entry with the icon.
#
#   ./install.sh               full install (uses sudo for system packages if available)
#   ./install.sh --no-system   skip system packages (no root? install them yourself first)
#   ./install.sh --uninstall   remove the menu entry, icon and .venv (settings in ~/.tadpole are kept)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
DESKTOP_FILE="$DATA_HOME/applications/tadpole.desktop"
ICON_FILE="$DATA_HOME/icons/hicolor/256x256/apps/tadpole.png"

usage() {
    sed -n '2,7p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

refresh_desktop_caches() {
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$DATA_HOME/applications" 2>/dev/null || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -t "$DATA_HOME/icons/hicolor" 2>/dev/null || true
    fi
}

uninstall() {
    echo "==> Removing menu entry, icon and virtual environment"
    rm -f "$DESKTOP_FILE" "$ICON_FILE"
    rm -rf "$ROOT/.venv"
    refresh_desktop_caches
    echo "Done. Your settings in ~/.tadpole were left alone; delete that folder to remove them too."
}

SYSTEM=auto
for arg in "$@"; do
    case "$arg" in
        --no-system) SYSTEM=skip ;;
        --uninstall) uninstall; exit 0 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $arg" >&2; usage >&2; exit 2 ;;
    esac
done

install_system_packages() {
    local sudo_cmd=()
    if [[ "$(id -u)" -ne 0 ]]; then
        if command -v sudo >/dev/null 2>&1; then
            sudo_cmd=(sudo)
        else
            echo "!! No root and no sudo: skipping system packages." >&2
            echo "   Ask an admin to install: python3 (3.10+), Tkinter, venv support, adb, fastboot." >&2
            return 0
        fi
    fi
    echo "==> Installing system packages"
    if command -v apt-get >/dev/null 2>&1; then
        "${sudo_cmd[@]}" apt-get update
        "${sudo_cmd[@]}" apt-get install -y python3 python3-tk python3-venv adb fastboot
        # udev rules so a normal user can talk to the phone over USB (package name varies by release)
        "${sudo_cmd[@]}" apt-get install -y android-sdk-platform-tools-common 2>/dev/null || true
    elif command -v dnf >/dev/null 2>&1; then
        "${sudo_cmd[@]}" dnf install -y python3 python3-tkinter android-tools
    elif command -v pacman >/dev/null 2>&1; then
        "${sudo_cmd[@]}" pacman -S --needed --noconfirm python tk android-tools
    elif command -v zypper >/dev/null 2>&1; then
        "${sudo_cmd[@]}" zypper --non-interactive install python3 python3-tk android-tools
    else
        echo "!! Unsupported package manager. Install Python 3.10+, Tkinter, venv support, adb and fastboot manually." >&2
    fi
}

if [[ "$SYSTEM" == "skip" ]]; then
    echo "==> Skipping system packages (--no-system)"
else
    install_system_packages
fi

PYTHON="$(command -v python3 || true)"
if [[ -z "$PYTHON" ]]; then
    echo "python3 was not found. Install Python 3.10+ and run ./install.sh again." >&2
    exit 1
fi

if ! "$PYTHON" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    echo "Tadpole requires Python 3.10 or newer." >&2
    exit 1
fi

if ! "$PYTHON" -c 'import tkinter' >/dev/null 2>&1; then
    echo "Tkinter is not available for $PYTHON." >&2
    echo "Install it (Debian/Ubuntu: python3-tk, Fedora: python3-tkinter, Arch: tk) and run ./install.sh again." >&2
    exit 1
fi

for tool in adb fastboot; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "!! $tool is not on PATH yet. Tadpole will start but show a warning until it is installed." >&2
    fi
done

echo "==> Creating local virtual environment (.venv)"
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
    "$PYTHON" -m venv --system-site-packages "$ROOT/.venv" || {
        echo "Could not create a virtual environment. On Debian/Ubuntu install python3-venv." >&2
        exit 1
    }
fi

# Refresh pip inside the project environment and install the app plus its
# declared dependencies. System-site-packages keeps distro Tkinter available.
echo "==> Installing Tadpole and Python dependencies"
"$ROOT/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/.venv/bin/python" -m pip install -e .

chmod +x "$ROOT/install.sh" "$ROOT/scripts/run.sh"

echo "==> Adding Tadpole to the application menu"
"$ROOT/.venv/bin/python" -m tadpole --install-desktop
refresh_desktop_caches

echo
echo "Installation complete. Start Tadpole from your application menu, or with:"
echo "    $ROOT/scripts/run.sh"
echo "Or activate the environment and run the command:"
echo "    source .venv/bin/activate && tadpole"
echo "Check your setup any time with:  $ROOT/scripts/run.sh --check"
echo "If your phone is not detected over USB, see 'USB permissions' in the README."
echo "For Termux:X11, start the X server first and set DISPLAY=:0."
echo "To remove everything this script added:  $ROOT/install.sh --uninstall"
