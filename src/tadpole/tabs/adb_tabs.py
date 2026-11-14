"""ADB-mode tabs: Overview, Apps, Files, Shell, Logcat, Screen."""
from __future__ import annotations

import base64
import re
import shlex
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .. import adb, theme
from ..widgets import make_text, make_tree


class AdbTabs:
    """Mixin for App. Each ``b_*`` builds one tab and returns its refresh callback (or None)."""

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
        e = ttk.Entry(bar, textvariable=cwd, font=theme.MONO)
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
        e = ttk.Entry(f, font=theme.MONO)
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
        theme.tag_colors(out)

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

