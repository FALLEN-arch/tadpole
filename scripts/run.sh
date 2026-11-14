#!/usr/bin/env bash
cd "$(dirname "$0")/.." || exit 1
if ! python3 -c "import tkinterdnd2" >/dev/null 2>&1; then
    echo "Missing dependency: tkinterdnd2 (needed for drag and drop)." >&2
    echo "Install it with: pip install -r requirements.txt" >&2
    exit 1
fi
PYTHONPATH=src exec python3 -m tadpole "$@"
