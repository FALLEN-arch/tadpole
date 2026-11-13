"""Reusable UI widgets for Tadpole."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Callable, Optional

from ..utils.theme import (
    BG, PANEL, PANEL2, LINE, TX, MUT, ACC, ACCS, OK, WARN, ERR, TERM, ON_ACC,
    MONO_FONT, tag_colors, darken_combobox,
)


def make_text_widget(parent: tk.Widget, height: int = 10, **kwargs) -> tuple[ttk.Frame, tk.Text]:
    """Create a text widget with scrollbar and dark styling."""
    frame = ttk.Frame(parent)
    text = tk.Text(
        frame,
        height=height,
        bg=TERM,
        fg=MUT,
        insertbackground=TX,
        relief="flat",
        font=MONO_FONT,
        wrap="word",
        padx=8,
        pady=6,
        highlightthickness=1,
        highlightbackground=LINE,
        **kwargs
    )
    scrollbar = ttk.Scrollbar(frame, command=text.yview)
    text.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    text.pack(side="left", fill="both", expand=True)
    tag_colors(text)
    return frame, text


def make_tree_widget(
    parent: tk.Widget,
    columns: list[str],
    widths: list[int],
) -> tuple[ttk.Frame, ttk.Treeview]:
    """Create a treeview with scrollbar."""
    frame = ttk.Frame(parent)
    tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
    for col, width in zip(columns, widths):
        tree.heading(col, text=col.title())
        tree.column(col, width=width, anchor="w", stretch=(col == columns[0]))
    scrollbar = ttk.Scrollbar(frame, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    return frame, tree


class SideNav(ttk.Frame):
    """Sidebar navigation with a Notebook-like API."""

    def __init__(self, parent: tk.Widget, on_change: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self._on_change = on_change

        self.side = ttk.Frame(self, style="Side.TFrame", padding=(8, 12))
        self.side.pack(side="left", fill="y")

        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True, padx=(16, 0))

        self.head = ttk.Label(right, style="Head.TLabel")
        self.head.pack(anchor="w", pady=(2, 10))

        self.stage = ttk.Frame(right)
        self.stage.pack(fill="both", expand=True)

        self.tabs: list[tuple[ttk.Frame, ttk.Button]] = []
        self.current: Optional[int] = None

    def add(self, frame: ttk.Frame, text: str) -> None:
        """Add a tab."""
        idx = len(self.tabs)
        button = ttk.Button(
            self.side,
            text=text,
            style="Nav.Toolbutton",
            width=18,
            command=lambda: self.select(idx),
        )
        button.pack(fill="x", pady=1)
        self.tabs.append((frame, button))
        if self.current is None:
            self.select(idx, notify=False)

    def select(self, idx: Optional[int] = None, notify: bool = True) -> str:
        """Select a tab by index."""
        if idx is None:
            return str(self.tabs[self.current][0]) if self.current is not None else ""

        for n, (frame, button) in enumerate(self.tabs):
            if n == idx:
                frame.pack(in_=self.stage, fill="both", expand=True)
                button.state(["selected"])
                self.head.configure(text=button.cget("text").split(None, 1)[-1])
            else:
                frame.pack_forget()
                button.state(["!selected"])
        self.current = idx
        if notify and self._on_change:
            self._on_change()
        return str(self.tabs[idx][0])

    @property
    def selected_frame(self) -> Optional[ttk.Frame]:
        """Get currently selected frame."""
        if self.current is not None:
            return self.tabs[self.current][0]
        return None


class Toolbar(ttk.Frame):
    """Simple toolbar with buttons."""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent)
        self.buttons: dict[str, ttk.Button] = {}

    def add_button(
        self,
        name: str,
        text: str,
        command: Callable[[], None],
        style: str = "TButton",
        side: str = "left",
        padx: int = 3,
    ) -> ttk.Button:
        """Add a button to the toolbar."""
        btn = ttk.Button(self, text=text, style=style, command=command)
        btn.pack(side=side, padx=padx)
        self.buttons[name] = btn
        return btn

    def add_separator(self, side: str = "left", padx: int = 8) -> ttk.Separator:
        """Add a vertical separator."""
        sep = ttk.Separator(self, orient="vertical")
        sep.pack(side=side, fill="y", padx=padx)
        return sep


class StatusPill(ttk.Label):
    """Status indicator pill."""

    def __init__(self, parent: tk.Widget, **kwargs):
        super().__init__(parent, style="Pill.TLabel", **kwargs)

    def set_ready(self, count: int) -> None:
        """Set ready state with device count."""
        if count > 0:
            self.configure(text=f"●  {count} ready", foreground=OK)
        else:
            self.configure(text="●  no device", foreground=WARN)

    def set_disconnected(self) -> None:
        """Set disconnected state."""
        self.configure(text="●  no device", foreground=MUT)


def confirm_dialog(
    parent: tk.Widget,
    title: str,
    message: str,
    confirm_word: str,
) -> bool:
    """Show a confirmation dialog requiring typed confirmation."""
    result = simpledialog.askstring(
        title,
        f"{message}\n\nType {confirm_word} to confirm:",
        parent=parent,
    )
    return result == confirm_word


def ask_string(parent: tk.Widget, title: str, prompt: str) -> Optional[str]:
    """Ask for a string input."""
    return simpledialog.askstring(title, prompt, parent=parent)


def ask_yes_no(parent: tk.Widget, title: str, message: str) -> bool:
    """Ask a yes/no question."""
    return messagebox.askyesno(title, message, parent=parent)


def show_error(parent: tk.Widget, title: str, message: str) -> None:
    """Show an error dialog."""
    messagebox.showerror(title, message, parent=parent)


def show_info(parent: tk.Widget, title: str, message: str) -> None:
    """Show an info dialog."""
    messagebox.showinfo(title, message, parent=parent)


def show_warning(parent: tk.Widget, title: str, message: str) -> None:
    """Show a warning dialog."""
    messagebox.showwarning(title, message, parent=parent)


def ask_save_file(
    parent: tk.Widget,
    title: str = "Save",
    initialfile: str = "",
    defaultextension: str = "",
    filetypes: Optional[list[tuple[str, str]]] = None,
) -> Optional[str]:
    """Ask for a file to save to."""
    return filedialog.asksaveasfilename(
        title=title,
        initialfile=initialfile,
        defaultextension=defaultextension,
        filetypes=filetypes,
        parent=parent,
    )


def ask_open_file(
    parent: tk.Widget,
    title: str = "Open",
    filetypes: Optional[list[tuple[str, str]]] = None,
) -> Optional[str]:
    """Ask for a file to open."""
    return filedialog.askopenfilename(title=title, filetypes=filetypes, parent=parent)
