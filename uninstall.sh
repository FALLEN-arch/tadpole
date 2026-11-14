#!/usr/bin/env bash
# Uninstall Tadpole: remove the project virtual environment and optional config.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "==> Removing project virtual environment (.venv)"
rm -rf "$ROOT/.venv"

echo "==> Removing build artifacts"
rm -rf "$ROOT/build" "$ROOT/dist" "$ROOT/src/tadpole.egg-info" 2>/dev/null || true

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