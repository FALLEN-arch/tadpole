"""Theme constants and utilities for the dark Sun Valley theme."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


# Dark palette (matches the Sun Valley dark theme from sv-ttk)
BG = "#1c1c1c"
PANEL = "#232323"
PANEL2 = "#2b2b2b"
LINE = "#3a3a3a"
TX = "#fafafa"
MUT = "#a0a0a0"
ACC = "#57c8ff"
ACCS = "#1f3a47"
OK = "#6ccb5f"
WARN = "#fce100"
ERR = "#ff99a4"
TERM = "#161616"
ON_ACC = "#1c1c1c"  # text colour on top of the accent colour

# Fonts
MONO_FONT = ("DejaVu Sans Mono", 10)
HEADING_FONT = ("TkDefaultFont", 17, "bold")
BIG_FONT = ("TkDefaultFont", 13, "bold")
PILL_FONT = ("TkDefaultFont", 11, "bold")


def apply_dark_theme(root: tk.Tk) -> None:
    """Apply the dark theme to the root window and configure ttk styles."""
    import sv_ttk

    root.configure(bg=BG)
    sv_ttk.set_theme("dark")

    style = ttk.Style(root)

    # Configure custom styles
    style.configure("Nav.Toolbutton", anchor="w", padding=(14, 9))
    style.configure("Side.TFrame", background=PANEL)
    style.configure("Top.TFrame", background=PANEL)
    style.configure("Top.TLabel", background=PANEL, foreground=TX, font=("TkDefaultFont", 12, "bold"))
    style.configure("Pill.TLabel", background=PANEL, foreground=MUT, font=PILL_FONT)
    style.configure("Tile.TFrame", background=BG, relief="solid", borderwidth=1, bordercolor=LINE)
    style.configure("Tile.TLabel", background=BG, foreground=MUT)
    style.configure("Big.TLabel", background=BG, foreground=TX, font=BIG_FONT)
    style.configure("BigBg.TLabel", foreground=TX, font=BIG_FONT)
    style.configure("Head.TLabel", foreground=TX, font=HEADING_FONT)
    style.configure("Mut.TLabel", foreground=MUT)
    style.configure("Danger.TButton", foreground=ERR)
    style.map("Danger.TButton", foreground=[("disabled", MUT), ("!disabled", ERR)])

    # Increase default font sizes
    import tkinter.font as tkfont
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(name).configure(size=11)


def darken_combobox(widget: tk.Widget) -> None:
    """Recursively apply dark styling to all combobox dropdowns."""
    if isinstance(widget, ttk.Combobox):
        try:
            popdown = widget.tk.call("ttk::combobox::PopdownWindow", str(widget))
            widget.tk.call(
                popdown + ".f.l", "configure",
                "-background", PANEL2, "-foreground", TX,
                "-selectbackground", ACC, "-selectforeground", ON_ACC,
                "-highlightthickness", 0, "-borderwidth", 0, "-activestyle", "none"
            )
            widget.tk.call(popdown, "configure", "-background", LINE)
        except tk.TclError:
            pass
    for child in widget.winfo_children():
        darken_combobox(child)


def tag_colors(text_widget: tk.Text) -> None:
    """Configure color tags for a text widget."""
    for tag, color in (
        ("cmd", ACC), ("ok", OK), ("err", ERR), ("warn", WARN),
        ("E", ERR), ("W", WARN), ("I", TX), ("D", MUT), ("V", MUT)
    ):
        text_widget.tag_configure(tag, foreground=color)
