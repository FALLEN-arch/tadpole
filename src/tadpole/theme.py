"""Colour palettes. Read colours as ``theme.BG`` etc. so a theme switch is seen everywhere."""
from __future__ import annotations

PALETTES = {
    "dark": dict(BG="#0b0d12", PANEL="#11141b", PANEL2="#1a1f2a", LINE="#2a303d", TX="#e6e9f0", MUT="#8a93a6",
                 ACC="#5b8cff", ACCS="#1c2740", OK="#3ddc97", WARN="#f5b84a", ERR="#ff5d6c", TERM="#080a0e"),
    "light": dict(BG="#f4f6fa", PANEL="#ffffff", PANEL2="#eceff5", LINE="#d5dae5", TX="#171b26", MUT="#5d667a",
                  ACC="#3b6df0", ACCS="#e3ebff", OK="#12a36a", WARN="#b7791f", ERR="#d93a4a", TERM="#f0f2f7"),
}

MONO = ("DejaVu Sans Mono", 10)


def set_palette(name):
    globals().update(PALETTES[name])


def tag_colors(t):
    for tag, col in (("cmd", ACC), ("ok", OK), ("err", ERR), ("warn", WARN), ("E", ERR), ("W", WARN)):  # noqa: F821
        t.tag_configure(tag, foreground=col)


set_palette("dark")
