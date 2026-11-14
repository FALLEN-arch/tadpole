"""A tiny fake of tkinter / ttk / tkinterdnd2 so the GUI code can be built without a display.

Every widget accepts any constructor arguments and any method call. This is not a
rendering test: it executes the code that builds each tab, which catches NameErrors,
bad imports and wrong attribute use after refactors.
"""
import sys
import types
from contextlib import contextmanager


class Widget:
    def __init__(self, *args, **kwargs):
        self._kw = kwargs

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *a, **k: Widget()

    def __getitem__(self, key):
        return None

    def __setitem__(self, key, value):
        pass

    def winfo_children(self):
        return []

    def get(self, *args):
        return ""

    def get_children(self, *args):
        return ()

    def selection(self):
        return ()

    def cget(self, key):
        return "icon Label"

    def nametowidget(self, name):
        return self


class Var:
    def __init__(self, *args, value=None, **kwargs):
        self._v = value

    def get(self):
        return self._v

    def set(self, v):
        self._v = v

    def trace_add(self, *args):
        pass


class TclError(Exception):
    pass


def _module(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    return mod


def build_modules():
    tk = _module("tkinter", Tk=Widget, Text=Widget, PhotoImage=Widget, StringVar=Var, BooleanVar=Var,
                 TclError=TclError)
    ttk = _module("tkinter.ttk")
    ttk.__getattr__ = lambda name: Widget  # PEP 562: any ttk class is a Widget
    font = _module("tkinter.font", nametofont=lambda n: Widget())
    dialogs = {n: _module("tkinter." + n) for n in ("filedialog", "messagebox", "simpledialog")}
    dnd = _module("tkinterdnd2", DND_FILES="DND_Files", TkinterDnD=types.SimpleNamespace(Tk=Widget))
    tk.ttk, tk.font = ttk, font
    for n, m in dialogs.items():
        setattr(tk, n, m)
    mods = {"tkinter": tk, "tkinter.ttk": ttk, "tkinter.font": font, "tkinterdnd2": dnd}
    mods.update({"tkinter." + n: m for n, m in dialogs.items()})
    return mods


@contextmanager
def fake_tk():
    """Install the fake modules and drop every tadpole GUI module imported under them afterwards."""
    saved = {k: sys.modules.get(k) for k in build_modules()}
    sys.modules.update(build_modules())
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        for k in [k for k in sys.modules if k.startswith("tadpole.") and k.split(".")[1] in
                  ("app", "tabs", "widgets")]:
            del sys.modules[k]
