#!/usr/bin/env bash
# Uninstall Tadpole: remove the project virtual environment, desktop entry, and icon.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "==> Removing project virtual environment (.venv)"
rm -rf "$ROOT/.venv"

echo "==> Removing build artifacts"
rm -rf "$ROOT/build" "$ROOT/dist" "$ROOT/src/tadpole.egg-info" 2>/dev/null || true

echo "==> Removing application menu entry and icon"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
DESKTOP_FILE="$DATA_HOME/applications/tadpole.desktop"
ICON_FILE="$DATA_HOME/icons/hicolor/256x256/apps/tadpole.png"
rm -f "$DESKTOP_FILE" "$ICON_FILE"
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DATA_HOME/applications" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t "$DATA_HOME/icons/hicolor" 2>/dev/null || true
fi

read -rp "Also remove Tadpole config directory ~/.tadpole (presets, theme)? [y/N] " ans
if [[ "${ans,,}" == "y" ]]; then
    rm -rf "$HOME/.tadpole"
    echo "Removed ~/.tadpole"
fi

# Check for legacy config
if [[ -d "$HOME/.adb-studio" ]]; then
    read -rp "Also remove legacy config directory ~/.adb-studio? [y/N] " ans
    if [[ "${ans,,}" == "y" ]]; then
        rm -rf "$HOME/.adb-studio"
        echo "Removed ~/.adb-studio"
    fi
fi

echo
echo "Uninstall complete."
echo "Note: System packages (python3, adb, fastboot, etc.) were NOT removed."
echo "Use your distribution's package manager if you want to remove those."