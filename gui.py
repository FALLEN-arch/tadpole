#!/usr/bin/env python3
"""Tadpole - native desktop GUI for adb and fastboot (Tkinter + tkinterdnd2)."""
from __future__ import annotations

import base64
import collections
import json
import re
import shlex
import subprocess
import threading
import queue
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import adb
from . import fastboot as fb

from tkinterdnd2 import DND_FILES, TkinterDnD  # required: drag and drop is a core feature

BaseTk = TkinterDnD.Tk

PALETTES = {
    "dark": dict(BG="#0b0d12", PANEL="#11141b", PANEL2="#1a1f2a", LINE="#2a303d", TX="#e6e9f0", MUT="#8a93a6",
                 ACC="#5b8cff", ACCS="#1c2740", OK="#3ddc97", WARN="#f5b84a", ERR="#ff5d6c", TERM="#080a0e"),
    "light": dict(BG="#f4f6fa", PANEL="#ffffff", PANEL2="#eceff5", LINE="#d5dae5", TX="#171b26", MUT="#5d667a",
                  ACC="#3b6df0", ACCS="#e3ebff", OK="#12a36a", WARN="#b7791f", ERR="#d93a4a", TERM="#f0f2f7"),
}


def set_palette(name):
    globals().update(PALETTES[name])


set_palette("dark")
CONF = Path.home() / ".tadpole"
if not CONF.exists() and (Path.home() / ".adb-studio").is_dir():
    CONF = Path.home() / ".adb-studio"  # settings from before the rename
TEXTS: list = []


def load_json(name, default):
    try:
        data = json.loads((CONF / name).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default
    return data if isinstance(data, type(default)) else default


def save_json(name, data):
    try:
        CONF.mkdir(parents=True, exist_ok=True)
        (CONF / name).write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def flash_pct(line, st):
    """Estimate flash progress (0-100) from a fastboot output line, or None."""
    m = re.search(r"Sending sparse '[^']*' (\d+)/(\d+)", line)
    if m:
        st["i"], st["n"] = int(m.group(1)), int(m.group(2))
        return (st["i"] - 0.5) / st["n"] * 100
    if line.startswith("Sending"):
        return (st["i"] - 0.5) / st["n"] * 100
    if line.startswith("Writing"):
        return st["i"] / st["n"] * 100
    if line.startswith("Finished"):
        return 100.0
    return None


def tag_colors(t):
    for tag, col in (("cmd", ACC), ("ok", OK), ("err", ERR), ("warn", WARN), ("E", ERR), ("W", WARN)):
        t.tag_configure(tag, foreground=col)


MONO = ("DejaVu Sans Mono", 10)
NAME_RE = re.compile(r"[A-Za-z0-9_]{1,40}")


def human(n: int) -> str:
    if not n:
        return "-"
    for u in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or u == "TiB":
            return f"{n:.0f} {u}" if n >= 10 or u == "B" else f"{n:.1f} {u}"
        n /= 1024


def make_text(parent, height=10, **kw):
    fr = ttk.Frame(parent)
    t = tk.Text(fr, height=height, bg=TERM, fg=MUT, insertbackground=TX, relief="flat",
                font=MONO, wrap="word", padx=8, pady=6, highlightthickness=1,
                highlightbackground=LINE, **kw)
    sb = ttk.Scrollbar(fr, command=t.yview)
    t.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    t.pack(side="left", fill="both", expand=True)
    tag_colors(t)
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


class App(BaseTk):
    def __init__(self):
        super().__init__()
        self.title("Tadpole")
        self.geometry("1100x740")
        self.minsize(760, 520)
        self.q: queue.Queue = queue.Queue()
        self.mode = tk.StringVar(value="adb")
        self.devmap: dict[str, str] = {}
        self.devsig = None
        self.fbvars = None
        self.fbfor = None
        self.preset = tk.StringVar()
        self.hist: list = []
        self.hi = 0
        self.lasterr = None
        self.logproc = None
        self.logbuf: collections.deque = collections.deque(maxlen=20000)
        self.shot = None
        self.theme = load_json("config.json", {}).get("theme", "dark")
        set_palette(self.theme if self.theme in PALETTES else "dark")
        self.presets: dict = load_json("presets.json", {})
        self.flashpath = None
        self.style_ui()
        self.build()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(50, self.pump)
        self.poll()

    # ------------------------------------------------------------ plumbing
    def on_close(self):
        self.stop_log()
        self.destroy()

    def style_ui(self):
        import tkinter.font as tkfont
        for n in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            tkfont.nametofont(n).configure(size=11)
        s = ttk.Style(self)
        s.theme_use("clam")
        self.configure(bg=BG)
        s.configure(".", background=BG, foreground=TX, fieldbackground=PANEL2, bordercolor=LINE,
                    lightcolor=PANEL, darkcolor=PANEL, troughcolor=PANEL2, focuscolor=BG)
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", padding=(16, 8), background=PANEL, foreground=MUT, borderwidth=0)
        s.map("TNotebook.Tab", background=[("selected", PANEL2)], foreground=[("selected", TX)])
        s.configure("TButton", padding=(12, 6), background=PANEL2, foreground=TX, borderwidth=1)
        s.map("TButton", background=[("active", LINE)])
        s.configure("Accent.TButton", background=ACC, foreground="#ffffff")
        s.map("Accent.TButton", background=[("active", "#7aa2ff")])
        s.configure("Danger.TButton", foreground=ERR)
        s.configure("Mode.TRadiobutton", padding=(14, 6), background=PANEL2, foreground=MUT)
        s.configure("Toolbutton", padding=(14, 6))
        s.configure("TCheckbutton", background=BG, foreground=TX)
        s.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TX, rowheight=26, borderwidth=0)
        s.configure("Treeview.Heading", background=PANEL2, foreground=MUT, relief="flat", padding=6)
        s.map("Treeview", background=[("selected", ACC)], foreground=[("selected", "#fff")])
        s.configure("Card.TFrame", background=PANEL, relief="solid", borderwidth=1)
        s.configure("Top.TFrame", background=PANEL)
        s.configure("Top.TLabel", background=PANEL, foreground=TX, font=("TkDefaultFont", 12, "bold"))
        s.configure("Card.TLabel", background=PANEL, foreground=MUT)
        s.configure("Big.TLabel", background=PANEL, foreground=TX, font=("TkDefaultFont", 13, "bold"))
        s.configure("BigBg.TLabel", background=BG, foreground=TX, font=("TkDefaultFont", 13, "bold"))
        s.configure("Mut.TLabel", foreground=MUT)
        s.configure("Side.TFrame", background=PANEL)
        s.configure("Nav.TButton", background=PANEL, foreground=MUT, anchor="w", padding=(14, 11), borderwidth=0, relief="flat")
        s.map("Nav.TButton", background=[("active", PANEL2)], foreground=[("active", TX)])
        s.configure("NavOn.TButton", background=ACCS, foreground=ACC, anchor="w", padding=(14, 11), borderwidth=0, relief="flat")
        s.map("NavOn.TButton", background=[("active", ACCS)], foreground=[("active", ACC)])
        s.configure("Head.TLabel", font=("TkDefaultFont", 17, "bold"), foreground=TX)
        s.configure("Pill.TLabel", background=PANEL, foreground=MUT, font=("TkDefaultFont", 11, "bold"))
        s.configure("TCombobox", arrowcolor=TX, background=PANEL2, foreground=TX, fieldbackground=PANEL2,
                    selectbackground=PANEL2, selectforeground=TX, bordercolor=LINE)
        s.map("TCombobox", fieldbackground=[("readonly", PANEL2), ("disabled", PANEL)],
              foreground=[("readonly", TX), ("disabled", MUT)], background=[("readonly", PANEL2), ("active", LINE)],
              selectbackground=[("readonly", PANEL2)], selectforeground=[("readonly", TX)])
        s.configure("TEntry", fieldbackground=PANEL2, foreground=TX, insertcolor=TX, bordercolor=LINE)
        s.configure("TScrollbar", background=PANEL2, troughcolor=PANEL, arrowcolor=MUT, bordercolor=PANEL, lightcolor=PANEL2, darkcolor=PANEL2)
        s.map("TScrollbar", background=[("active", LINE)])
        s.configure("TProgressbar", background=ACC, troughcolor=PANEL2, bordercolor=LINE)
        s.configure("TPanedwindow", background=BG)
        s.configure("Sash", background=LINE)
        self.option_add("*TCombobox*Listbox.background", PANEL2)
        self.option_add("*TCombobox*Listbox.foreground", TX)
        self.option_add("*TCombobox*Listbox.selectBackground", ACC)

    def pump(self):
        while True:
            try:
                fn = self.q.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                # A bad callback (e.g. a corrupt screenshot) must not stop the
                # pump, or the whole UI would silently freeze.
                try:
                    self.log("error", f"{type(exc).__name__}: {exc}", "err")
                except Exception:  # noqa: BLE001
                    pass
        self.after(50, self.pump)

    def log(self, cmd, out="", tag=""):
        t = self.term
        t.configure(state="normal")
        t.insert("end", f"$ {cmd}\n", "cmd")
        if out:
            t.insert("end", out.rstrip() + "\n", tag)
        t.see("end")
        t.configure(state="disabled")

    def bg(self, fn, done=None, cmd=None):
        def work():
            try:
                res, err = fn(), None
            except Exception as exc:  # noqa: BLE001
                res, err = None, exc

            def fin():
                if cmd:
                    self.log(cmd, str(err) if err else (res if isinstance(res, str) and res else "OK"),
                             "err" if err else "ok")
                elif err:
                    self.log("error", str(err), "err")
                if done and not err:
                    done(res)
            self.q.put(fin)
        threading.Thread(target=work, daemon=True).start()

    @property
    def ser(self):
        return self.devmap.get(self.devbox.get())

    def need(self):
        s = self.ser
        if not s:
            self.log("no device", "Select a device first.", "warn")
        return s

    def adb(self, args, done=None, timeout=60):
        s = self.need()
        if s:
            self.bg(lambda: adb.run(s, args, timeout), done, f"adb -s {s} {' '.join(args)}")

    def fbr(self, args, done=None, timeout=300):
        s = self.need()
        if s:
            self.bg(lambda: fb.run(s, args, timeout), done, f"fastboot -s {s} {' '.join(args)}")

    def typed(self, title, msg, word):
        return simpledialog.askstring(title, f"{msg}\n\nType {word} to confirm:", parent=self) == word

    # ------------------------------------------------------------ layout
    def build(self):
        top = ttk.Frame(self, style="Top.TFrame", padding=(14, 10))
        top.pack(fill="x")
        ttk.Label(top, text="Tadpole", style="Top.TLabel").pack(side="left", padx=(0, 16))
        for text, val in (("ADB", "adb"), ("Fastboot", "fb")):
            ttk.Radiobutton(top, text=text, value=val, variable=self.mode, style="Toolbutton",
                            command=self.switch).pack(side="left", padx=2)
        self.devbox = ttk.Combobox(top, state="readonly", width=44)
        self.devbox.pack(side="left", padx=14)
        self.devbox.bind("<<ComboboxSelected>>", lambda e: self.refresh_tab())
        ttk.Button(top, text="Refresh", command=self.poll_now).pack(side="left")
        self.pill = ttk.Label(top, text="●  no device", style="Pill.TLabel")
        self.pill.pack(side="left", padx=14)
        self.themebtn = ttk.Button(top, text="☀ Light" if self.theme == "dark" else "☾ Dark", command=self.toggle_theme)
        self.themebtn.pack(side="right", padx=6)
        self.wifi = ttk.Frame(top, style="Top.TFrame")
        self.wifi.pack(side="right")
        ttk.Button(self.wifi, text="Connect…", command=self.connect).pack(side="left", padx=3)
        ttk.Button(self.wifi, text="Pair…", command=self.pair).pack(side="left", padx=3)
        ttk.Button(self.wifi, text="Restart server", command=self.restart).pack(side="left", padx=3)

        paned = ttk.PanedWindow(self, orient="vertical")
        paned.pack(fill="both", expand=True, padx=10, pady=10)
        self.body = ttk.Frame(paned)
        paned.add(self.body, weight=4)
        dock = ttk.Frame(paned)
        paned.add(dock, weight=1)
        hd = ttk.Frame(dock)
        hd.pack(fill="x", pady=(0, 4))
        ttk.Label(hd, text="TERMINAL", style="Mut.TLabel").pack(side="left")
        ttk.Button(hd, text="Clear", command=self.clear_term).pack(side="right")
        fr, self.term = make_text(dock, height=8, state="disabled")
        fr.pack(fill="both", expand=True)
        self.cmd = ttk.Entry(dock, font=MONO)
        self.cmd.pack(fill="x", pady=(6, 0))
        self.cmd.bind("<Return>", self.run_cmd)
        self.cmd.bind("<Up>", lambda e: self.hist_nav(-1))
        self.cmd.bind("<Down>", lambda e: self.hist_nav(1))

        self.fbhint = ttk.Label(self.body, style="Mut.TLabel", wraplength=900, justify="left",
                                text="No fastboot device found. Boot the phone into the bootloader (power off, "
                                     "then hold Vol− + Power), connect USB, then press Refresh. "
                                     "From the ADB tab you can also use Overview ▸ Bootloader.")
        self.nb = {"adb": SideNav(self.body), "fb": SideNav(self.body)}
        for key, tabs in (("adb", [("◈  Overview", self.b_overview), ("▦  Apps", self.b_apps), ("▤  Files", self.b_files),
                                  ("❯  Shell", self.b_shell), ("☰  Logcat", self.b_logcat), ("▣  Screen", self.b_screen)]),
                          ("fb", [("◈  Device", self.b_fbdevice), ("⚡  Flash", self.b_flash), ("▤  Partitions", self.b_parts),
                                  ("⚿  Bootloader", self.b_boot), ("⟳  Reboot", self.b_reboot)])):
            for title, builder in tabs:
                f = ttk.Frame(self.nb[key], padding=14)
                f.on_show = builder(f) or (lambda: None)
                self.nb[key].add(f, text=title)
            self.nb[key].on_change = self.refresh_tab
        self.switch()
        self.log("ready", "Pick a device above. Terminal accepts adb / fastboot commands.")
        self.enable_dnd()

    def switch(self):
        self.stop_log()
        for k, n in self.nb.items():
            n.pack_forget()
        self.nb[self.mode.get()].pack(fill="both", expand=True)
        self.update_hint()
        if self.mode.get() == "adb":
            self.wifi.pack(side="right")
        else:
            self.wifi.pack_forget()
        self.cmd.delete(0, "end")
        self.devsig = None
        self.devbox.set("")
        self.fbvars = None
        self.poll_now()

    def update_hint(self):
        if self.mode.get() == "fb" and not self.ser:
            self.fbhint.pack(side="top", fill="x", pady=(0, 6), before=self.nb["fb"])
        else:
            self.fbhint.pack_forget()

    def refresh_tab(self):
        nb = self.nb[self.mode.get()]
        try:
            nb.nametowidget(nb.select()).on_show()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------ devices
    def poll_now(self):
        m = self.mode.get()

        def work():
            try:
                devs = adb.devices() if m == "adb" else fb.devices()
                self.lasterr = None
                return devs
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                if msg != self.lasterr:
                    self.lasterr = msg
                    self.q.put(lambda: self.log("adb" if m == "adb" else "fastboot", msg, "err"))
                return []

        def done(devs):
            if m != self.mode.get():
                return
            sig = [(d["serial"], d["state"]) for d in devs]
            if sig == self.devsig:
                return
            self.devsig = sig
            self.devmap = {f"{d.get('model') or d['serial']}  ·  {d['serial']}  ·  {d['state']}": d["serial"] for d in devs}
            ready = [d for d in devs if d["state"] in ("device", "fastboot")]
            self.pill.configure(text=f"●  {len(ready)} ready" if ready else "●  no device",
                                foreground=OK if ready else (WARN if devs else MUT))
            keep = self.devbox.get()
            self.devbox["values"] = list(self.devmap)
            self.devbox.set(keep if keep in self.devmap else (next(iter(self.devmap), "")))
            self.update_hint()
            self.refresh_tab()
        self.bg(work, done)

    def poll(self):
        self.poll_now()
        self.after(4000, self.poll)

    def connect(self):
        a = simpledialog.askstring("Connect", "Device address (ip:port):", parent=self)
        if a:
            def work():
                out = adb.run(None, ["connect", a.strip()], 20)
                # `adb connect` exits 0 even on failure, so check the text
                if re.search(r"failed|cannot|unable|refused|error", out, re.I):
                    raise adb.AdbError(out.strip())
                return out
            self.bg(work, lambda r: self.poll_now(), f"adb connect {a}")

    def pair(self):
        a = simpledialog.askstring("Pair", "Pairing address (ip:port):", parent=self)
        c = a and simpledialog.askstring("Pair", "Pairing code:", parent=self)
        if a and c:
            self.bg(lambda: adb.run(None, ["pair", a.strip(), c.strip()], 30), None, f"adb pair {a} ******")

    def restart(self):
        def work():
            adb.run(None, ["kill-server"])
            return adb.run(None, ["start-server"])
        self.bg(work, lambda r: self.poll_now(), "adb kill-server && adb start-server")

    def toggle_theme(self):
        self.apply_theme("light" if self.theme == "dark" else "dark")

    def apply_theme(self, name):
        self.theme = name
        set_palette(name)
        self.style_ui()
        for t in TEXTS:
            try:
                t.configure(bg=TERM, fg=MUT, insertbackground=TX, highlightbackground=LINE)
                tag_colors(t)
            except tk.TclError:
                pass
        self.themebtn.configure(text="☀ Light" if name == "dark" else "☾ Dark")
        save_json("config.json", {"theme": name})
        self.devsig = None
        self.poll_now()

    def enable_dnd(self):
        def reg(w):
            try:
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self.on_drop)
            except Exception:  # noqa: BLE001
                pass
            for c in w.winfo_children():
                reg(c)
        reg(self)

    def on_drop(self, e):
        files = list(self.tk.splitlist(e.data))
        if self.mode.get() == "adb":
            apks = [p for p in files if p.lower().endswith(".apk")]
            if apks:
                self.install_many(apks)
            else:
                self.log("drop", "In ADB mode, drop .apk files to install them.", "warn")
        else:
            imgs = [p for p in files if p.lower().endswith((".img", ".bin"))]
            if imgs and self.flashpath is not None:
                self.flashpath.set(imgs[0])
                stem = Path(imgs[0]).stem
                if NAME_RE.fullmatch(stem):
                    self.preset.set(stem)
                self.nb["fb"].select(1)
                self.log("drop", f"Loaded {imgs[0]} into Flash.", "ok")
            else:
                self.log("drop", "In Fastboot mode, drop an .img file to prepare a flash.", "warn")

    def install_many(self, paths):
        s = self.need()
        if not s or not paths:
            return

        def work():
            try:
                return adb.run(s, ["install", "-r", paths[0]], 600)
            finally:
                self.q.put(lambda: self.install_many(paths[1:]))
        self.bg(work, None, f"adb -s {s} install -r {paths[0]}")

    def clear_term(self):
        self.term.configure(state="normal")
        self.term.delete("1.0", "end")
        self.term.configure(state="disabled")

    def hist_nav(self, d):
        if not self.hist:
            return "break"
        self.hi = max(0, min(len(self.hist), self.hi + d))
        self.cmd.delete(0, "end")
        if self.hi < len(self.hist):
            self.cmd.insert(0, self.hist[self.hi])
        return "break"

    def run_cmd(self, _e):
        raw = self.cmd.get().strip()
        if raw:
            self.hist.append(raw)
            self.hi = len(self.hist)
        try:
            a = shlex.split(raw)
        except ValueError as exc:
            self.log(raw, str(exc), "err")
            return
        self.cmd.delete(0, "end")
        tool = self.mode.get()
        if a and a[0] in ("adb", "fastboot"):
            tool = "adb" if a.pop(0) == "adb" else "fb"

        # Respect an explicitly supplied serial instead of silently running
        # the command against the device selected in the GUI.
        serial = self.ser
        if a and a[0] == "-s":
            if len(a) < 3 or not a[1]:
                self.log(raw, "Expected a device serial after -s.", "err")
                return
            serial = a[1]
            del a[:2]
        if not a:
            return

        is_adb = tool == "adb"
        runner = adb.run if is_adb else fb.run
        global_command = a[0] in (("devices", "version", "--version") if is_adb else ("devices", "--version"))
        command = "adb" if is_adb else "fastboot"
        target = None if global_command else serial
        suffix = f" -s {target}" if target else ""
        self.bg(lambda: runner(target, a, 120), None, f"{command}{suffix} {' '.join(a)}")

    # ------------------------------------------------------------ ADB tabs
    def b_overview(self, f):
        vals = {k: tk.StringVar(value="-") for k in ("Model", "Brand", "Android", "ABI", "Screen", "Battery", "Status", "Temperature")}
        g = ttk.Frame(f)
        g.pack(fill="x")
        for i, (k, v) in enumerate(vals.items()):
            c = ttk.Frame(g, style="Card.TFrame", padding=12)
            c.grid(row=i // 4, column=i % 4, sticky="nsew", padx=5, pady=5)
            g.columnconfigure(i % 4, weight=1)
            ttk.Label(c, text=k, style="Card.TLabel").pack(anchor="w")
            ttk.Label(c, textvariable=v, style="Big.TLabel").pack(anchor="w")
        row = ttk.Frame(f)
        row.pack(fill="x", pady=14)
        for t, a in (("Reboot", ["reboot"]), ("Bootloader", ["reboot", "bootloader"]), ("Recovery", ["reboot", "recovery"]),
                     ("Wake", ["shell", "input", "keyevent", "KEYCODE_WAKEUP"]), ("Sleep", ["shell", "input", "keyevent", "KEYCODE_SLEEP"])):
            ttk.Button(row, text=t, command=lambda a=a: self.adb(a)).pack(side="left", padx=4)
        row2 = ttk.Frame(f)
        row2.pack(fill="x")
        ttk.Button(row2, text="Restart adbd as root", command=lambda: self.adb(["root"])).pack(side="left", padx=4)
        ttk.Button(row2, text="Sideload ZIP", command=lambda: (lambda p: p and self.adb(["sideload", p], None, 1800))(filedialog.askopenfilename(filetypes=[("ZIP", "*.zip")]))).pack(side="left", padx=4)

        def refresh():
            s = self.ser
            if not s:
                return

            def work():
                return adb.snapshot(s)

            def done(r):
                i, b, sz = r
                vals["Model"].set(i["model"] or "-"); vals["Brand"].set(i["brand"] or "-")
                vals["Android"].set(f"{i['android']} (SDK {i['sdk']})"); vals["ABI"].set(i["abi"] or "-")
                vals["Screen"].set(sz or "-"); vals["Battery"].set(b.get("level") or "-")
                vals["Status"].set(b.get("status") or "-"); vals["Temperature"].set(b.get("temperature") or "-")
            self.bg(work, done)
        return refresh

    def b_apps(self, f):
        kind, q, pkgs = tk.StringVar(value="-3"), tk.StringVar(), []
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 8))
        for t, v in (("Third-party", "-3"), ("System", "-s"), ("All", "")):
            ttk.Radiobutton(bar, text=t, value=v, variable=kind, style="Toolbutton", command=lambda: load()).pack(side="left", padx=2)
        ttk.Entry(bar, textvariable=q, width=26).pack(side="left", padx=10)
        bar2 = ttk.Frame(f)
        bar2.pack(fill="x", pady=(0, 8))
        ttk.Label(bar2, text="Tip: drop .apk files anywhere in this window", style="Mut.TLabel").pack(side="right")
        fr, tree = make_tree(f, ("package",), (500,))
        shown: list[str] = []

        def draw(*_):
            tree.delete(*tree.get_children())
            shown[:] = [p for p in pkgs if q.get().lower() in p.lower()]
            for i, p in enumerate(shown):
                tree.insert("", "end", iid=str(i), values=(p,))
        q.trace_add("write", draw)

        def load():
            s = self.ser
            if s:
                def work():
                    out = adb.run(s, ["shell", "pm", "list", "packages"] + ([kind.get()] if kind.get() else []))
                    return sorted(l[8:].strip() for l in out.splitlines() if l.startswith("package:"))

                def done(r):
                    pkgs[:] = r
                    draw()
                self.bg(work, done)

        def sel():
            s = tree.selection()
            return shown[int(s[0])] if s else None

        def act(kindname):
            p = sel()
            if not p:
                return
            if kindname == "launch":
                self.adb(["shell", "monkey", "-p", p, "-c", "android.intent.category.LAUNCHER", "1"])
            elif kindname == "stop":
                self.adb(["shell", "am", "force-stop", p])
            elif kindname == "clear" and messagebox.askyesno("Clear data", f"Clear all data for {p}?"):
                self.adb(["shell", "pm", "clear", p])
            elif kindname == "apk":
                s = self.need()
                if not s:
                    return

                def done(remote):
                    dest = filedialog.asksaveasfilename(initialfile=p + ".apk")
                    if dest:
                        self.adb(["pull", remote, dest], None, 600)
                self.bg(lambda: adb.run(s, ["shell", "pm", "path", p]).splitlines()[0].replace("package:", "").strip(), done)
            elif kindname in ("disable", "enable"):
                self.adb(["shell", "pm", kindname if kindname == "enable" else "disable-user", "--user", "0", p])
            elif kindname == "uninstall" and messagebox.askyesno("Uninstall", f"Uninstall {p}?"):
                self.adb(["shell", "pm", "uninstall", p], lambda r: load())

        def install():
            path = filedialog.askopenfilename(filetypes=[("APK", "*.apk")])
            if path:
                self.adb(["install", "-r", path], lambda r: load(), 600)
        for t, k, st in (("Launch", "launch", ""), ("Stop", "stop", ""), ("Clear data", "clear", ""), ("Pull APK…", "apk", ""),
                         ("Disable", "disable", ""), ("Enable", "enable", ""), ("Uninstall", "uninstall", "Danger.TButton")):
            ttk.Button(bar2, text=t, style=st or "TButton", command=lambda k=k: act(k)).pack(side="left", padx=3)
        ttk.Button(bar, text="Install APK…", style="Accent.TButton", command=install).pack(side="right")
        fr.pack(fill="both", expand=True)
        return load

    def b_files(self, f):
        cwd, rows = tk.StringVar(value="/sdcard"), []
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 8))
        fr, tree = make_tree(f, ("name", "type"), (500, 90))

        def load():
            s = self.ser
            if not s:
                return
            path = cwd.get()

            def work():
                out = adb.run(s, ["shell", "ls", "-1p", shlex.quote(path)])
                items = [(n.strip().rstrip("/"), n.strip().endswith("/")) for n in out.splitlines() if n.strip() not in ("", ".", "..")]
                return sorted(items, key=lambda e: (not e[1], e[0].lower()))

            def done(r):
                rows[:] = r
                tree.delete(*tree.get_children())
                for i, (n, d) in enumerate(r):
                    tree.insert("", "end", iid=str(i), values=(n, "folder" if d else "file"))
            self.bg(work, done)

        def sel():
            s = tree.selection()
            return rows[int(s[0])] if s else None

        def join(n):
            return cwd.get().rstrip("/") + "/" + n

        def up():
            cwd.set(re.sub(r"/[^/]+/?$", "", cwd.get()) or "/")
            load()

        def enter(_e=None):
            r = sel()
            if r and r[1]:
                cwd.set(join(r[0]))
                load()

        def pull():
            r = sel()
            if r and not r[1]:
                dest = filedialog.asksaveasfilename(initialfile=r[0])
                if dest:
                    self.adb(["pull", join(r[0]), dest], None, 600)

        def push():
            src = filedialog.askopenfilename()
            if src:
                self.adb(["push", src, cwd.get()], lambda r: load(), 600)

        def delete():
            r = sel()
            if r and messagebox.askyesno("Delete", f"Delete {join(r[0])}?"):
                self.adb(["shell", "rm", "-rf", shlex.quote(join(r[0]))], lambda x: load())
        ttk.Button(bar, text="Up", command=up).pack(side="left")
        e = ttk.Entry(bar, textvariable=cwd, font=MONO)
        e.pack(side="left", fill="x", expand=True, padx=8)
        e.bind("<Return>", lambda _e: load())
        for t, c, st in (("Pull…", pull, "TButton"), ("Push…", push, "Accent.TButton"), ("Delete", delete, "Danger.TButton")):
            ttk.Button(bar, text=t, command=c, style=st).pack(side="left", padx=3)
        tree.bind("<Double-1>", enter)
        fr.pack(fill="both", expand=True)
        return load

    def b_shell(self, f):
        fr, out = make_text(f, state="disabled")
        fr.pack(fill="both", expand=True)
        e = ttk.Entry(f, font=MONO)
        e.pack(fill="x", pady=(8, 0))
        hint = [True]
        out.configure(state="normal"); out.insert("end", "Type a command below and press Enter, e.g.  getprop ro.product.model\n"); out.configure(state="disabled")

        def run(_e):
            s, t = self.need(), e.get().strip()
            if not (s and t):
                return
            e.delete(0, "end")

            def done(r):
                out.configure(state="normal")
                if hint[0]:
                    out.delete("1.0", "end"); hint[0] = False
                out.insert("end", f"$ {t}\n", "cmd"); out.insert("end", r.rstrip() + "\n"); out.see("end"); out.configure(state="disabled")
            self.bg(lambda: adb.run(s, ["shell", t], 120), done, f"adb -s {s} shell {t}")
        e.bind("<Return>", run)

    def stop_log(self):
        if self.logproc:
            try:
                self.logproc.terminate()
            except Exception:  # noqa: BLE001
                pass
            self.logproc = None

    def b_logcat(self, f):
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 8))
        flt, lvl, find = tk.StringVar(), tk.StringVar(value="V"), tk.StringVar()
        ttk.Label(bar, text="Level", style="Mut.TLabel").pack(side="left")
        ttk.Combobox(bar, textvariable=lvl, values=list("VDIWEF"), width=3, state="readonly", justify="center").pack(side="left", padx=(6, 18))
        ttk.Label(bar, text="Filter", style="Mut.TLabel").pack(side="left")
        ttk.Entry(bar, textvariable=flt, width=22).pack(side="left", padx=(6, 18))
        ttk.Label(bar, text="Find", style="Mut.TLabel").pack(side="left")
        ttk.Entry(bar, textvariable=find, width=18).pack(side="left", padx=6)
        bar2 = ttk.Frame(f)
        bar2.pack(fill="x", pady=(0, 8))
        fr, out = make_text(f)
        order = "VDIWEF"
        hint = [True]
        out.insert("end", "Press Start to stream logcat.\nFilter takes logcat specs, e.g.  ActivityManager:I *:S\n")
        out.tag_configure("E", foreground=ERR); out.tag_configure("W", foreground=WARN)

        def start():
            s = self.need()
            if not s:
                return
            try:
                extra = shlex.split(flt.get())
            except ValueError as exc:
                return self.log("logcat filter", str(exc), "err")
            self.stop_log()
            self.logbuf.clear()
            if hint[0]:
                out.delete("1.0", "end")
                hint[0] = False
            proc = subprocess.Popen([adb.adb_path(), "-s", s, "logcat", "-v", "threadtime"] + extra,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.logproc = proc

            def reader():
                for raw in iter(proc.stdout.readline, b""):
                    self.logbuf.append(raw.decode("utf-8", "replace").rstrip())
            threading.Thread(target=reader, daemon=True).start()

            def flush():
                if self.logproc is not proc:
                    return
                n = 0
                while self.logbuf and n < 400:
                    line = self.logbuf.popleft(); n += 1
                    m = re.match(r"^\S+\s+\S+\s+\d+\s+\d+\s+([VDIWEF])\s", line)
                    L = m.group(1) if m else "I"
                    if order.index(L) >= order.index(lvl.get()) and find.get().lower() in line.lower():
                        out.insert("end", line + "\n", L)
                if n:
                    if int(out.index("end-1c").split(".")[0]) > 5000:
                        out.delete("1.0", "1500.0")
                    out.see("end")
                self.after(120, flush)
            flush()
        ttk.Button(bar2, text="Start", style="Accent.TButton", command=start).pack(side="left", padx=3)
        ttk.Button(bar2, text="Stop", command=self.stop_log).pack(side="left", padx=3)
        ttk.Button(bar2, text="Clear", command=lambda: out.delete("1.0", "end")).pack(side="left", padx=3)

        def save():
            p = filedialog.asksaveasfilename(initialfile="logcat.txt")
            if p:
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(out.get("1.0", "end"))
        ttk.Button(bar2, text="Save…", command=save).pack(side="left", padx=3)
        fr.pack(fill="both", expand=True)

    def b_screen(self, f):
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 6))
        keys = ttk.Frame(f)
        keys.pack(fill="x", pady=(0, 8))
        st = {"d": None, "k": 1, "busy": False}
        live = tk.BooleanVar()
        lab = ttk.Label(f, anchor="center", cursor="hand2", style="Mut.TLabel", text="Press Capture to grab the screen")

        def capture():
            s = self.ser
            if not s or st["busy"]:
                return
            st["busy"] = True

            def work():
                try:
                    return adb.run_bytes(s, ["exec-out", "screencap", "-p"])
                finally:
                    self.q.put(lambda: st.update(busy=False))

            def done(data):
                st["d"] = data
                img = tk.PhotoImage(data=base64.b64encode(data))
                k = max(1, -(-img.height() // max(200, f.winfo_height() - 150)))
                st["k"] = k
                self.shot = img.subsample(k) if k > 1 else img
                lab.configure(image=self.shot, text="")
            self.bg(work, done)

        def tick():
            if live.get() and self.mode.get() == "adb" and f.winfo_ismapped():
                capture()
            self.after(1500, tick)

        def tap(e):
            if not self.shot:
                return
            w, h = self.shot.width(), self.shot.height()
            x = (e.x - (lab.winfo_width() - w) / 2) * st["k"]
            y = (e.y - (lab.winfo_height() - h) / 2) * st["k"]
            if 0 <= x <= w * st["k"] and 0 <= y <= h * st["k"]:
                self.adb(["shell", "input", "tap", str(int(x)), str(int(y))], lambda r: self.after(500, capture))

        def key(code):
            self.adb(["shell", "input", "keyevent", str(code)], lambda r: self.after(500, capture))

        def save():
            if st["d"]:
                p = filedialog.asksaveasfilename(defaultextension=".png", initialfile="screenshot.png")
                if p:
                    with open(p, "wb") as fh:
                        fh.write(st["d"])
        ttk.Button(bar, text="Capture", style="Accent.TButton", command=capture).pack(side="left")
        ttk.Checkbutton(bar, text="Live (1.5 s)", variable=live).pack(side="left", padx=10)
        ttk.Button(bar, text="Save PNG…", command=save).pack(side="left")
        ttk.Label(bar, text="Click the screenshot to tap", style="Mut.TLabel").pack(side="right")
        for t, c in (("◀ Back", 4), ("● Home", 3), ("▣ Recents", 187), ("Power", 26), ("Vol +", 24), ("Vol −", 25)):
            ttk.Button(keys, text=t, command=lambda c=c: key(c)).pack(side="left", padx=3)
        lab.bind("<Button-1>", tap)
        lab.pack(fill="both", expand=True)
        tick()

    # ------------------------------------------------------------ fastboot tabs
    def load_vars(self, done, force=False):
        s = self.ser
        if not s:
            return
        if self.fbvars and self.fbfor == s and not force:
            return done(self.fbvars)

        def ok(v):
            self.fbvars, self.fbfor = v, s
            done(v)
        self.bg(lambda: fb.getvar_all(s), ok, f"fastboot -s {s} getvar all")

    def b_fbdevice(self, f):
        state = tk.StringVar(value="Bootloader state: unknown")
        ttk.Label(f, textvariable=state, style="BigBg.TLabel").pack(anchor="w", pady=(0, 8))
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 8))

        def save():
            p = filedialog.asksaveasfilename(initialfile="fastboot-vars.txt")
            if p:
                with open(p, "w", encoding="utf-8") as fh:
                    for i in tree.get_children():
                        fh.write("%s: %s\n" % tree.item(i, "values"))
        ttk.Button(bar, text="Refresh", command=lambda: refresh()).pack(side="left")
        ttk.Button(bar, text="Save report…", command=save).pack(side="left", padx=6)
        fr, tree = make_tree(f, ("variable", "value"), (260, 500))
        fr.pack(fill="both", expand=True)

        def refresh():
            def done(v):
                tree.delete(*tree.get_children())
                for k, val in sorted(v["vars"].items()):
                    tree.insert("", "end", values=(k, val))
                u = v["vars"].get("unlocked")
                state.set("Bootloader: " + ("UNLOCKED" if u == "yes" else "LOCKED" if u == "no" else "state unknown"))
            self.load_vars(done, True)
        return refresh

    def b_flash(self, f):
        slot, path = tk.StringVar(value="active"), tk.StringVar()
        vv, vf = tk.BooleanVar(), tk.BooleanVar()
        self.flashpath = path
        pb = ttk.Frame(f)
        pb.pack(anchor="w", pady=(0, 12))
        ttk.Label(pb, text="Preset", style="Mut.TLabel").pack(side="left")
        pc = ttk.Combobox(pb, values=sorted(self.presets), width=22, state="readonly")
        pc.pack(side="left", padx=8)

        def load_p():
            p = self.presets.get(pc.get())
            if p:
                self.preset.set(p.get("partition", ""))
                slot.set(p.get("slot", "active"))
                path.set(p.get("image", ""))
                vv.set(p.get("verity", False))
                vf.set(p.get("verification", False))

        def save_p():
            n = simpledialog.askstring("Save preset", "Preset name:", parent=self)
            if n and n.strip():
                self.presets[n.strip()] = {"partition": self.preset.get(), "slot": slot.get(), "image": path.get(),
                                           "verity": vv.get(), "verification": vf.get()}
                save_json("presets.json", self.presets)
                pc["values"] = sorted(self.presets)
                pc.set(n.strip())

        def del_p():
            n = pc.get()
            if n in self.presets and messagebox.askyesno("Delete preset", f"Delete preset '{n}'?"):
                del self.presets[n]
                save_json("presets.json", self.presets)
                pc["values"] = sorted(self.presets)
                pc.set("")
        ttk.Button(pb, text="Load", command=load_p).pack(side="left", padx=2)
        ttk.Button(pb, text="Save current…", command=save_p).pack(side="left", padx=2)
        ttk.Button(pb, text="Delete", style="Danger.TButton", command=del_p).pack(side="left", padx=2)
        g = ttk.Frame(f)
        g.pack(anchor="w")
        ttk.Label(g, text="Partition").grid(row=0, column=0, sticky="w", pady=6)
        cb = ttk.Combobox(g, textvariable=self.preset, width=28)
        cb.grid(row=0, column=1, padx=10, sticky="w")
        ttk.Label(g, text="Image").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(g, textvariable=path, width=44).grid(row=1, column=1, padx=10)
        ttk.Button(g, text="Browse…", command=lambda: path.set(filedialog.askopenfilename(filetypes=[("Images", "*.img *.bin"), ("All", "*")]) or path.get())).grid(row=1, column=2)
        ttk.Label(g, text="Slot").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Combobox(g, textvariable=slot, values=["active", "a", "b", "all"], state="readonly", width=10).grid(row=2, column=1, padx=10, sticky="w")
        ttk.Checkbutton(f, text="--disable-verity", variable=vv).pack(anchor="w")
        ttk.Checkbutton(f, text="--disable-verification", variable=vf).pack(anchor="w")
        prog = ttk.Progressbar(f, mode="determinate", maximum=100, length=320)
        pl = tk.StringVar()
        plab = ttk.Label(f, textvariable=pl, style="Mut.TLabel")

        def go():
            s, p, img = self.need(), self.preset.get().strip(), path.get().strip()
            if not s:
                return
            if not NAME_RE.fullmatch(p) or not img:
                return messagebox.showerror("Flash", "Enter a valid partition name and choose an image.")
            if not self.typed("Flash image", f"Write {img} to {p}. A wrong image can brick the device.", "FLASH"):
                return
            args = (["--slot", slot.get()] if slot.get() != "active" else []) + (["--disable-verity"] if vv.get() else []) + (["--disable-verification"] if vf.get() else []) + ["flash", p, img]
            prog.configure(value=0)
            pl.set("Flashing… 0%")
            prog.pack(anchor="w", pady=(10, 2))
            plab.pack(anchor="w")
            st = {"i": 1, "n": 1}

            def on_line(line):
                pct = flash_pct(line, st)
                if pct is not None:
                    self.q.put(lambda: (prog.configure(value=pct), pl.set(f"Flashing… {pct:.0f}%")))

            def work():
                try:
                    return fb.run_stream(s, args, on_line, 1800)
                finally:
                    self.q.put(lambda: (prog.pack_forget(), plab.pack_forget()))
            self.bg(work, None, f"fastboot -s {s} {' '.join(args)}")
        ttk.Button(f, text="Flash image", style="Accent.TButton", command=go).pack(anchor="w", pady=14)

        def refresh():
            def done(v):
                names = sorted({re.sub(r"_[ab]$", "", p["name"]) for p in v["partitions"]})
                cb["values"] = names or ["boot", "init_boot", "vendor_boot", "dtbo", "vbmeta", "recovery", "system", "vendor", "userdata"]
            self.load_vars(done)
        return refresh

    def b_parts(self, f):
        fr, tree = make_tree(f, ("partition", "size", "type"), (320, 120, 100))
        rows: list = []

        def sel():
            s = tree.selection()
            return rows[int(s[0])] if s else None

        def erase():
            p = sel()
            if p and self.typed("Erase partition", f"fastboot erase {p['name']} - data on it is lost.", "ERASE"):
                self.fbr(["erase", p["name"]])

        def flash():
            p = sel()
            if p:
                self.preset.set(re.sub(r"_[ab]$", "", p["name"]))
                nb = self.nb["fb"]
                nb.select(1)
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Button(bar, text="Flash selected…", command=flash).pack(side="left")
        ttk.Button(bar, text="Erase selected", style="Danger.TButton", command=erase).pack(side="left", padx=6)
        fr.pack(fill="both", expand=True)

        def refresh():
            def done(v):
                rows[:] = v["partitions"]
                tree.delete(*tree.get_children())
                for i, p in enumerate(rows):
                    tree.insert("", "end", iid=str(i), values=(p["name"], human(p.get("size", 0)), "logical" if p.get("logical") else "physical"))
            self.load_vars(done, True)
        return refresh

    def b_boot(self, f):
        def danger(label, args, word, msg):
            def run():
                if self.typed(label, msg, word):
                    self.fbr(args, lambda r: setattr(self, "fbvars", None))
            return run
        items = (("Unlock bootloader", ["flashing", "unlock"], "UNLOCK", "Unlocking wipes user data and weakens boot security.", "Danger.TButton"),
                 ("Lock bootloader", ["flashing", "lock"], "LOCK", "Locking with a modified system can brick the device.", "Danger.TButton"),
                 ("Wipe data (-w)", ["-w"], "WIPE", "This erases userdata and cache.", "Danger.TButton"))
        for t, a, w, m, st in items:
            ttk.Button(f, text=t, style=st, command=danger(t, a, w, m), width=26).pack(anchor="w", pady=5)
        ttk.Label(f, text="Active slot", style="Mut.TLabel").pack(anchor="w", pady=(16, 4))
        r = ttk.Frame(f)
        r.pack(anchor="w")
        for sl in ("a", "b"):
            ttk.Button(r, text=f"Set slot {sl}", command=lambda sl=sl: self.fbr(["set_active", sl])).pack(side="left", padx=(0, 6))

    def b_reboot(self, f):
        for t, a in (("Reboot to system", ["reboot"]), ("Reboot to bootloader", ["reboot", "bootloader"]),
                     ("Reboot to recovery", ["reboot", "recovery"]), ("Reboot to fastbootd", ["reboot", "fastboot"])):
            ttk.Button(f, text=t, width=26, command=lambda a=a: self.fbr(a)).pack(anchor="w", pady=5)


def main() -> None:
    try:
        App().mainloop()
    except tk.TclError as exc:
        raise SystemExit(f"Cannot open a window: {exc}\nOn Termux/proot start Termux:X11 first and run: export DISPLAY=:0")


if __name__ == "__main__":
    main()
