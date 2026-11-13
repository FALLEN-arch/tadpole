#!/usr/bin/env bash
# Tadpole installer: system packages + Python venv + Tadpole + desktop integration
set -euo pipefail
cd "$(dirname "$0")"

VENV_DIR="$HOME/.local/share/tadpole/venv"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
METAINFO_DIR="$HOME/.local/share/metainfo"
MAN_DIR="$HOME/.local/share/man/man1"

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
rm -f "$BIN_DIR/tadpole"
cat > "$BIN_DIR/tadpole" << 'LAUNCHER'
#!/usr/bin/env bash
exec "$HOME/.local/share/tadpole/venv/bin/python" -m tadpole "$@"
LAUNCHER
chmod +x "$BIN_DIR/tadpole"

echo "==> Installing desktop integration files"
mkdir -p "$DESKTOP_DIR" "$ICON_DIR" "$METAINFO_DIR" "$MAN_DIR"

# Desktop file
cp data/applications/com.fallen-arch.Tadpole.desktop "$DESKTOP_DIR/"

# Icon
cp data/icons/hicolor/scalable/apps/com.fallen-arch.Tadpole.svg "$ICON_DIR/"

# AppStream metainfo
cp data/metainfo/com.fallen-arch.Tadpole.metainfo.xml "$METAINFO_DIR/"

# Man page
cp man/tadpole.1 "$MAN_DIR/"

# Update caches
command -v update-desktop-database >/dev/null && update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -f -q "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
command -v mandb >/dev/null && mandb -q "$MAN_DIR" 2>/dev/null || true

echo
echo "Done. Run:"
echo "    tadpole"
echo
echo "If 'tadpole' isn't found, open a new terminal or run:"
echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
echo
echo "The app will also appear in your application menu under Development/System."
