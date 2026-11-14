"""Fastboot-mode tabs: Device, Flash, Partitions, Bootloader, Reboot."""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .. import fastboot as fb
from ..config import save_json
from ..util import NAME_RE, flash_pct, human
from ..widgets import make_tree


class FastbootTabs:
    """Mixin for App. Each ``b_*`` builds one tab and returns its refresh callback (or None)."""

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
                # Access cb via self.preset's widget to avoid stale closure reference
                for child in f.winfo_children():
                    if isinstance(child, ttk.Frame):
                        for widget in child.winfo_children():
                            if isinstance(widget, ttk.Combobox) and widget.cget("textvariable") == str(self.preset):
                                widget["values"] = names or ["boot", "init_boot", "vendor_boot", "dtbo", "vbmeta", "recovery", "system", "vendor", "userdata"]
                                break
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

