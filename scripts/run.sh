#!/usr/bin/env bash
# Run Tadpole from a checkout using a local venv
set -euo pipefail
cd "$(dirname "$0")/.." || exit 1

VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install -r requirements.txt
    "$VENV_DIR/bin/pip" install -e .
fi

exec "$VENV_DIR/bin/python" -m tadpole "$@"
