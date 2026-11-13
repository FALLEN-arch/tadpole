#!/usr/bin/env bash
# Tadpole installer: system packages (python3-tk, adb, fastboot, pipx) + Tadpole itself.
set -euo pipefail
cd "$(dirname "$0")"

if [ "$(id -u)" -eq 0 ]; then
    SUDO=""
elif command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
else
    echo "Run as root or install sudo first." >&2
    exit 1
fi

echo "==> Installing system packages"
if command -v apt-get >/dev/null 2>&1; then
    $SUDO apt-get update
    $SUDO apt-get install -y python3 python3-tk python3-venv pipx adb fastboot
elif command -v dnf >/dev/null 2>&1; then
    $SUDO dnf install -y python3 python3-tkinter pipx android-tools
elif command -v pacman >/dev/null 2>&1; then
    $SUDO pacman -S --needed --noconfirm python tk python-pipx android-tools
else
    echo "Unsupported package manager. Install python3, tkinter, pipx, adb and fastboot manually," >&2
    echo "then run: pipx install --system-site-packages ." >&2
    exit 1
fi

echo "==> Installing Tadpole and its Python dependencies (tkinterdnd2, sv-ttk, Pillow)"
pipx ensurepath >/dev/null 2>&1 || true
export PATH="$HOME/.local/bin:$PATH"
# --system-site-packages lets the isolated pipx venv see the system Tkinter
pipx install --system-site-packages --force .

echo
echo "Done. Run:"
echo "    tadpole"
echo "If 'tadpole' isn't found, open a new terminal or run: export PATH=\"\$HOME/.local/bin:\$PATH\""
