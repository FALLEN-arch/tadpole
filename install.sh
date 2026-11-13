#!/usr/bin/env bash
# Tadpole installer: system packages + Python venv + Tadpole
set -euo pipefail
cd "$(dirname "$0")"

VENV_DIR="$HOME/.local/share/tadpole/venv"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"

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
    $SUDO apt-get install -y python3 python3-tk python3-venv adb fastboot
elif command -v dnf >/dev/null 2>&1; then
    $SUDO dnf install -y python3 python3-tkinter python3-virtualenv android-tools
elif command -v pacman >/dev/null 2>&1; then
    $SUDO pacman -S --needed --noconfirm python tk python-virtualenv android-tools
else
    echo "Unsupported package manager. Install python3, tkinter, venv, adb and fastboot manually," >&2
    echo "then run: python3 -m venv ~/.local/share/tadpole/venv && ~/.local/share/tadpole/venv/bin/pip install ." >&2
    exit 1
fi

echo "==> Creating virtual environment"
python3 -m venv "$VENV_DIR"

echo "==> Installing Tadpole and dependencies"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install .

echo "==> Creating launcher script"
mkdir -p "$BIN_DIR"
# Remove any existing file/symlink first
rm -f "$BIN_DIR/tadpole"
cat > "$BIN_DIR/tadpole" << 'LAUNCHER'
#!/usr/bin/env bash
exec "$HOME/.local/share/tadpole/venv/bin/python" -m tadpole "$@"
LAUNCHER
chmod +x "$BIN_DIR/tadpole"

echo "==> Creating desktop entry"
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/tadpole.desktop" << DESKTOP
[Desktop Entry]
Name=Tadpole
Comment=Native GUI for adb and fastboot
Exec=$BIN_DIR/tadpole
Icon=phone
Terminal=false
Type=Application
Categories=Development;System;
DESKTOP

echo
echo "Done. Run:"
echo "    tadpole"
echo
echo "If 'tadpole' isn't found, open a new terminal or run:"
echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
