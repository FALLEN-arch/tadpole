"""Tadpole main window: top bar, mode switch, terminal dock and device polling."""
from __future__ import annotations

import collections
import queue
import re
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from tkinterdnd2 import DND_FILES, TkinterDnD  # required: drag and drop is a core feature

from . import adb, deps, theme
from . import fastboot as fb
from .config import load_json, save_json
from .tabs.adb_tabs import AdbTabs
from .tabs.fastboot_tabs import FastbootTabs
from .util import NAME_RE, parse_terminal
from .widgets import TEXTS, SideNav, make_text

BaseTk = TkinterDnD.Tk
ASSETS = Path(__file__).resolve().parent / "assets"


class App(BaseTk, AdbTabs, FastbootTabs):
    def __init__(self):
        # className sets WM_CLASS ("Tadpole") so desktops can match the window to tadpole.desktop
        super().__init__(className="tadpole")
        self.title("Tadpole")
        self.set_icon()
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
        theme.set_palette(self.theme if self.theme in theme.PALETTES else "dark")
        self.presets: dict = load_json("presets.json", {})
        self.flashpath = None
        self.style_ui()
        self.build()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(50, self.pump)
        self.poll()
        self.after(300, self.check_tools)

    def set_icon(self):
        """Use the bundled icon for the window / taskbar (several sizes; the WM picks the best)."""
        try:
            self._icons = [tk.PhotoImage(file=str(ASSETS / f"tadpole-{n}.png")) for n in (256, 64)]
            self.iconphoto(True, *self._icons)
        except (tk.TclError, OSError):
            pass  # a missing icon must never stop the app from starting

    def check_tools(self):
        """Tell the user up front if adb / fastboot are not installed."""
        missing = deps.missing_tools()
        if missing:
            msg = deps.tools_message(missing)
            self.log("setup", msg, "warn")
            messagebox.showwarning("Missing tools", msg, parent=self)

    def on_close(self):
        self.stop_log()
        self.destroy()

    def style_ui(self):
        import tkinter.font as tkfont
        for n in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            tkfont.nametofont(n).configure(size=11)
        s = ttk.Style(self)
        s.theme_use("clam")
        self.configure(bg=theme.BG)
        s.configure(".", background=theme.BG, foreground=theme.TX, fieldbackground=theme.PANEL2, bordercolor=theme.LINE,
                    lightcolor=theme.PANEL, darkcolor=theme.PANEL, troughcolor=theme.PANEL2, focuscolor=theme.BG)
        s.configure("TNotebook", background=theme.BG, borderwidth=0)
        s.configure("TNotebook.Tab", padding=(16, 8), background=theme.PANEL, foreground=theme.MUT, borderwidth=0)
        s.map("TNotebook.Tab", background=[("selected", theme.PANEL2)], foreground=[("selected", theme.TX)])
        s.configure("TButton", padding=(12, 6), background=theme.PANEL2, foreground=theme.TX, borderwidth=1)
        s.map("TButton", background=[("active", theme.LINE)])
        s.configure("Accent.TButton", background=theme.ACC, foreground="#ffffff")
        s.map("Accent.TButton", background=[("active", "#7aa2ff")])
        s.configure("Danger.TButton", foreground=theme.ERR)
        s.configure("Mode.TRadiobutton", padding=(14, 6), background=theme.PANEL2, foreground=theme.MUT)
        s.configure("Toolbutton", padding=(14, 6))
        s.configure("TCheckbutton", background=theme.BG, foreground=theme.TX)
        s.configure("Treeview", background=theme.PANEL, fieldbackground=theme.PANEL, foreground=theme.TX, rowheight=26, borderwidth=0)
        s.configure("Treeview.Heading", background=theme.PANEL2, foreground=theme.MUT, relief="flat", padding=6)
        s.map("Treeview", background=[("selected", theme.ACC)], foreground=[("selected", "#fff")])
        s.configure("Card.TFrame", background=theme.PANEL, relief="solid", borderwidth=1)
        s.configure("Top.TFrame", background=theme.PANEL)
        s.configure("Top.TLabel", background=theme.PANEL, foreground=theme.TX, font=("TkDefaultFont", 12, "bold"))
        s.configure("Card.TLabel", background=theme.PANEL, foreground=theme.MUT)
        s.configure("Big.TLabel", background=theme.PANEL, foreground=theme.TX, font=("TkDefaultFont", 13, "bold"))
        s.configure("BigBg.TLabel", background=theme.BG, foreground=theme.TX, font=("TkDefaultFont", 13, "bold"))
        s.configure("Mut.TLabel", foreground=theme.MUT)
        s.configure("Side.TFrame", background=theme.PANEL)
        s.configure("Nav.TButton", background=theme.PANEL, foreground=theme.MUT, anchor="w", padding=(14, 11), borderwidth=0, relief="flat")
        s.map("Nav.TButton", background=[("active", theme.PANEL2)], foreground=[("active", theme.TX)])
        s.configure("NavOn.TButton", background=theme.ACCS, foreground=theme.ACC, anchor="w", padding=(14, 11), borderwidth=0, relief="flat")
        s.map("NavOn.TButton", background=[("active", theme.ACCS)], foreground=[("active", theme.ACC)])
        s.configure("Head.TLabel", font=("TkDefaultFont", 17, "bold"), foreground=theme.TX)
        s.configure("Pill.TLabel", background=theme.PANEL, foreground=theme.MUT, font=("TkDefaultFont", 11, "bold"))
        s.configure("TCombobox", arrowcolor=theme.TX, background=theme.PANEL2, foreground=theme.TX, fieldbackground=theme.PANEL2,
                    selectbackground=theme.PANEL2, selectforeground=theme.TX, bordercolor=theme.LINE)
        s.map("TCombobox", fieldbackground=[("readonly", theme.PANEL2), ("disabled", theme.PANEL)],
              foreground=[("readonly", theme.TX), ("disabled", theme.MUT)], background=[("readonly", theme.PANEL2), ("active", theme.LINE)],
              selectbackground=[("readonly", theme.PANEL2)], selectforeground=[("readonly", theme.TX)])
        s.configure("TEntry", fieldbackground=theme.PANEL2, foreground=theme.TX, insertcolor=theme.TX, bordercolor=theme.LINE)
        s.configure("TScrollbar", background=theme.PANEL2, troughcolor=theme.PANEL, arrowcolor=theme.MUT, bordercolor=theme.PANEL, lightcolor=theme.PANEL2, darkcolor=theme.PANEL2)
        s.map("TScrollbar", background=[("active", theme.LINE)])
        s.configure("TProgressbar", background=theme.ACC, troughcolor=theme.PANEL2, bordercolor=theme.LINE)
        s.configure("TPanedwindow", background=theme.BG)
        s.configure("Sash", background=theme.LINE)
        self.option_add("*TCombobox*Listbox.background", theme.PANEL2)
        self.option_add("*TCombobox*Listbox.foreground", theme.TX)
        self.option_add("*TCombobox*Listbox.selectBackground", theme.ACC)

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
                # Log to stderr as well so UI bugs surface during development.
                import sys
                print(f"pump callback error: {type(exc).__name__}: {exc}", file=sys.stderr)
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
        self.cmd = ttk.Entry(dock, font=theme.MONO)
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
                                foreground=theme.OK if ready else (theme.WARN if devs else theme.MUT))
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
        theme.set_palette(name)
        self.style_ui()
        for t in TEXTS:
            try:
                t.configure(bg=theme.TERM, fg=theme.MUT, insertbackground=theme.TX, highlightbackground=theme.LINE)
                theme.tag_colors(t)
            except tk.TclError:
                pass
        self.themebtn.configure(text="☀ Light" if name == "dark" else "☾ Dark")
        save_json("config.json", {"theme": name})
        self.devsig = None
        self.poll_now()

    def enable_dnd(self):
        # Only register the toplevel window and the body frame for DnD.
        # Walking the entire widget tree recursively is expensive and unnecessary;
        # TkinterDnD events bubble up from children.
        for w in (self, self.body):
            try:
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self.on_drop)
            except Exception:  # noqa: BLE001
                pass

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
        # hi points to the *next* entry to show; valid range is 0..len(hist)-1
        # when hi == len(hist), we're at the "new command" position (empty entry)
        self.hi = max(0, min(len(self.hist) - 1, self.hi + d))
        self.cmd.delete(0, "end")
        self.cmd.insert(0, self.hist[self.hi])
        return "break"

    def run_cmd(self, _e):
        raw = self.cmd.get().strip()
        if raw:
            self.hist.append(raw)
            self.hi = len(self.hist)
        try:
            parsed = parse_terminal(raw, self.mode.get(), self.ser)
        except ValueError as exc:
            self.log(raw, str(exc), "err")
            return
        self.cmd.delete(0, "end")
        if not parsed:
            return
        tool, serial, a = parsed
        runner = adb.run if tool == "adb" else fb.run
        command = "adb" if tool == "adb" else "fastboot"
        suffix = f" -s {serial}" if serial else ""
        self.bg(lambda: runner(serial, a, 120), None, f"{command}{suffix} {' '.join(a)}")


def main() -> None:
    try:
        App().mainloop()
    except tk.TclError as exc:
        raise SystemExit(f"Cannot open a window: {exc}\nOn Termux/proot start Termux:X11 first and run: export DISPLAY=:0")
