#!/usr/bin/env bash
# Install system tools and create a project-local Python virtual environment.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ "$(id -u)" -eq 0 ]]; then
    SUDO=()
elif command -v sudo >/dev/null 2>&1; then
    SUDO=(sudo)
else
    echo "Run as root or install sudo first." >&2
    exit 1
fi

install_system_packages() {
    echo "==> Installing system packages"
    if command -v apt-get >/dev/null 2>&1; then
        "${SUDO[@]}" apt-get update
        "${SUDO[@]}" apt-get install -y python3 python3-tk python3-venv adb fastboot
    elif command -v dnf >/dev/null 2>&1; then
        "${SUDO[@]}" dnf install -y python3 python3-tkinter android-tools
    elif command -v pacman >/dev/null 2>&1; then
        "${SUDO[@]}" pacman -S --needed --noconfirm python tk android-tools
    else
        echo "Unsupported package manager. Install Python 3.10+, Tkinter, venv support, adb and fastboot manually." >&2
        exit 1
    fi
}

install_system_packages

PYTHON="$(command -v python3 || true)"
if [[ -z "$PYTHON" ]]; then
    echo "python3 was not found after installing system packages." >&2
    exit 1
fi

if ! "$PYTHON" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    echo "Tadpole requires Python 3.10 or newer." >&2
    exit 1
fi

echo "==> Creating local virtual environment (.venv)"
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
    "$PYTHON" -m venv --system-site-packages "$ROOT/.venv"
fi

# Refresh pip inside the project environment and install the app plus its
# declared dependencies. System-site-packages keeps distro Tkinter available.
echo "==> Installing Tadpole and Python dependencies"
"$ROOT/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/.venv/bin/python" -m pip install -e .

chmod +x "$ROOT/install.sh" "$ROOT/scripts/run.sh"

echo
echo "Installation complete. Start Tadpole with:"
echo "    $ROOT/scripts/run.sh"
echo "Or activate the environment and run the command:"
echo "    source .venv/bin/activate && tadpole"
echo "For Termux:X11, start the X server first and set DISPLAY=:0."
