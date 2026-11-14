"""Reusable Tk widgets and constructors shared by the tabs."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import theme

TEXTS: list = []  # every themed Text widget, so a theme switch can recolour them


def make_text(parent, height=10, **kw):
    fr = ttk.Frame(parent)
    t = tk.Text(fr, height=height, bg=theme.TERM, fg=theme.MUT, insertbackground=theme.TX, relief="flat",
                font=theme.MONO, wrap="word", padx=8, pady=6, highlightthickness=1,
                highlightbackground=theme.LINE, **kw)
    sb = ttk.Scrollbar(fr, command=t.yview)
    t.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    t.pack(side="left", fill="both", expand=True)
    theme.tag_colors(t)
    TEXTS.append(t)
    return fr, t


def make_tree(parent, cols, widths):
    fr = ttk.Frame(parent)
    t = ttk.Treeview(fr, columns=cols, show="headings", selectmode="browse")
    for c, w in zip(cols, widths):
        t.heading(c, text=c.title())
        t.column(c, width=w, anchor="w", stretch=(c == cols[0]))
    sb = ttk.Scrollbar(fr, command=t.yview)
    t.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    t.pack(side="left", fill="both", expand=True)
    return fr, t


class SideNav(ttk.Frame):
    """Sidebar navigation with a Notebook-like API (add / select)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.side = ttk.Frame(self, style="Side.TFrame", padding=(8, 12))
        self.side.pack(side="left", fill="y")
        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True, padx=(16, 0))
        self.head = ttk.Label(right, style="Head.TLabel")
        self.head.pack(anchor="w", pady=(2, 10))
        self.stage = ttk.Frame(right)
        self.stage.pack(fill="both", expand=True)
        self.tabs: list = []
        self.cur = None
        self.on_change = None

    def add(self, frame, text):
        i = len(self.tabs)
        b = ttk.Button(self.side, text=text, style="Nav.TButton", width=18, command=lambda: self.select(i))
        b.pack(fill="x", pady=1)
        self.tabs.append((frame, b))
        if self.cur is None:
            self.select(i, notify=False)

    def select(self, i=None, notify=True):
        if i is None:
            return str(self.tabs[self.cur][0]) if self.cur is not None else ""
        for n, (fr, b) in enumerate(self.tabs):
            if n == i:
                fr.pack(in_=self.stage, fill="both", expand=True)
                b.configure(style="NavOn.TButton")
                self.head.configure(text=b.cget("text").split(None, 1)[-1])
            else:
                fr.pack_forget()
                b.configure(style="Nav.TButton")
        self.cur = i
        if notify and self.on_change:
            self.on_change()

