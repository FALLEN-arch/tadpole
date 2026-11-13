#!/usr/bin/env bash
cd "$(dirname "$0")/.." || exit 1
if ! python3 -c "import tkinterdnd2, sv_ttk, PIL" >/dev/null 2>&1; then
    echo "Missing Python dependencies (tkinterdnd2, sv-ttk, Pillow)." >&2
    echo "Install them with: pip install -r requirements.txt" >&2
    exit 1
fi
PYTHONPATH=src exec python3 -m tadpole "$@"
