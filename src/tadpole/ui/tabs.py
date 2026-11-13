"""Tab implementations for Tadpole."""
from __future__ import annotations

import io
import re
import shlex
import threading
import tkinter as tk
from collections import deque
from pathlib import Path
from tkinter import ttk
from typing import Optional, Callable

from PIL import Image, ImageTk

from ..models.device import Device
from ..models.app import AppInfo
from ..models.file import FileInfo
from ..models.flash import FlashOptions, FlashPreset
from ..models.partition import Partition
from ..services.adb_service import AdbService, AdbError
from ..services.fastboot_service import FastbootService, FastbootError
from ..services.preset_service import PresetService
from ..utils.theme import (
    BG, PANEL, PANEL2, LINE, TX, MUT, ACC, ACCS, OK, WARN, ERR, TERM, ON_ACC,
    MONO_FONT, HEADING_FONT, BIG_FONT, tag_colors, darken_combobox,
)
from ..utils.validation import NAME_RE, validate_partition_name
from .widgets import (
    make_text_widget,
    make_tree_widget,
    Toolbar,
    confirm_dialog,
    ask_string,
    ask_yes_no,
    show_error,
    ask_save_file,
    ask_open_file,
)


class TabBase(ttk.Frame):
    """Base class for all tabs."""

    def __init__(
        self,
        parent: tk.Widget,
        app: "MainWindow",
        service: Optional[object] = None,
    ):
        super().__init__(parent, padding=14)
        self.app = app
        self.service = service
        self._visible = False

    def on_show(self) -> None:
        """Called when tab becomes visible."""
        self._visible = True
        self.refresh()

    def on_hide(self) -> None:
        """Called when tab is hidden."""
        self._visible = False

    def refresh(self) -> None:
        """Refresh tab content. Override in subclasses."""
        pass

    def require_device(self) -> Optional[str]:
        """Get current device serial or show error."""
        serial = self.app.current_serial
        if not serial:
            self.app.log("error", "Select a device first.", "warn")
        return serial


# ============================================================
# ADB Tabs
# ============================================================

class AdbOverviewTab(TabBase):
    """Device overview tab."""

    def __init__(self, parent: tk.Widget, app: "MainWindow", adb: AdbService):
        super().__init__(parent, app, adb)
        self._build_ui()

    def _build_ui(self) -> None:
        # Device info tile
        self.info_frame = ttk.Frame(self, style="Tile.TFrame", padding=16)
        self.info_frame.pack(fill="x", pady=(0, 12))

        ttk.Label(self.info_frame, text="Device Info", style="Big.TLabel").pack(anchor="w")
        self.model_label = ttk.Label(self.info_frame, text="", style="BigBg.TLabel")
        self.model_label.pack(anchor="w", pady=(4, 0))

        self.detail_frame = ttk.Frame(self.info_frame)
        self.detail_frame.pack(fill="x", pady=(8, 0))

        self.brand_var = tk.StringVar()
        self.android_var = tk.StringVar()
        self.sdk_var = tk.StringVar()
        self.abi_var = tk.StringVar()
        self.battery_var = tk.StringVar()
        self.screen_var = tk.StringVar()

        for label, var in (
            ("Brand", self.brand_var),
            ("Android", self.android_var),
            ("SDK", self.sdk_var),
            ("ABI", self.abi_var),
            ("Battery", self.battery_var),
            ("Screen", self.screen_var),
        ):
            row = ttk.Frame(self.detail_frame)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=f"{label}:", style="Mut.TLabel", width=10).pack(side="left")
            ttk.Label(row, textvariable=var, style="Tile.TLabel").pack(side="left")

        # Actions
        action_frame = ttk.Frame(self)
        action_frame.pack(fill="x", pady=(0, 12))

        actions = [
            ("Reboot to Bootloader", lambda: self._reboot("bootloader")),
            ("Reboot to Recovery", lambda: self._reboot("recovery")),
            ("Reboot to Fastbootd", lambda: self._reboot("fastboot")),
            ("Reboot System", lambda: self._reboot("")),
        ]
        for text, cmd in actions:
            ttk.Button(action_frame, text=text, command=cmd, width=22).pack(side="left", padx=3)

        # Buttons row 2
        action_frame2 = ttk.Frame(self)
        action_frame2.pack(fill="x")
        ttk.Button(action_frame2, text="ADB Root", command=self._root, width=22).pack(side="left", padx=3)
        ttk.Button(action_frame2, text="Sideload ZIP…", command=self._sideload, width=22).pack(side="left", padx=3)

    def _reboot(self, target: str) -> None:
        serial = self.require_device()
        if not serial:
            return
        self.app.run_bg(
            lambda: self.service.run(serial, ["reboot"] + ([target] if target else [])),
            lambda r: self.app.log("adb reboot", r, "ok"),
            f"adb -s {serial} reboot {target}",
        )

    def _root(self) -> None:
        serial = self.require_device()
        if not serial:
            return
        self.app.run_bg(
            lambda: self.service.root(serial),
            lambda r: self.app.log("adb root", r, "ok"),
            f"adb -s {serial} root",
        )

    def _sideload(self) -> None:
        serial = self.require_device()
        if not serial:
            return
        path = ask_open_file(self, "Sideload ZIP", [("ZIP files", "*.zip"), ("All files", "*.*")])
        if not path:
            return
        self.app.run_bg(
            lambda: self.service.sideload(serial, path),
            lambda r: self.app.log("adb sideload", r, "ok"),
            f"adb -s {serial} sideload {path}",
        )

    def refresh(self) -> None:
        serial = self.app.current_serial
        if not serial:
            self._clear()
            return

        def work():
            info = self.service.get_device_info(serial)
            battery = self.service.get_battery(serial)
            screen = self.service.get_screen_size(serial)
            return info, battery, screen

        def done(result):
            info, battery, screen = result
            self.model_label.configure(text=info.display_name or serial)
            self.brand_var.set(info.brand or "-")
            self.android_var.set(info.android or "-")
            self.sdk_var.set(info.sdk or "-")
            self.abi_var.set(info.abi or "-")
            self.battery_var.set(f"{battery.level} {battery.status} {battery.temperature}".strip() or "-")
            self.screen_var.set(screen or "-")

        self.app.run_bg(work, done)

    def _clear(self) -> None:
        self.model_label.configure(text="No device selected")
        for var in (self.brand_var, self.android_var, self.sdk_var, self.abi_var, self.battery_var, self.screen_var):
            var.set("-")


class AdbAppsTab(TabBase):
    """Apps management tab."""

    def __init__(self, parent: tk.Widget, app: "MainWindow", adb: AdbService):
        super().__init__(parent, app, adb)
        self.apps: list[AppInfo] = []
        self._build_ui()

    def _build_ui(self) -> None:
        # Toolbar
        bar = Toolbar(self)
        bar.pack(fill="x", pady=(0, 8))

        bar.add_button("refresh", "Refresh", self.refresh, side="left")
        bar.add_button("install", "Install APK…", self._install_apk, style="Accent.TButton", side="right")

        # Tree
        frame, self.tree = make_tree_widget(
            self, ("package", "version", "state"), (400, 120, 100)
        )
        frame.pack(fill="both", expand=True)

        # Action buttons
        bar2 = Toolbar(self)
        bar2.pack(fill="x", pady=(8, 0))

        for name, text, style in (
            ("launch", "Launch", "TButton"),
            ("stop", "Stop", "TButton"),
            ("clear", "Clear Data", "TButton"),
            ("uninstall", "Uninstall", "Danger.TButton"),
            ("disable", "Disable", "TButton"),
            ("enable", "Enable", "TButton"),
            ("pull_apk", "Pull APK…", "TButton"),
        ):
            bar2.add_button(name, text, lambda n=name: self._act(n), style=style)

        self.tree.bind("<Double-1>", lambda e: self._act("launch"))

    def _act(self, action: str) -> None:
        serial = self.require_device()
        if not serial:
            return
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx >= len(self.apps):
            return
        app = self.apps[idx]

        cmds = {
            "launch": (lambda: self.service.launch_app(serial, app.package), f"Launch {app.package}"),
            "stop": (lambda: self.service.stop_app(serial, app.package), f"Stop {app.package}"),
            "clear": (lambda: self.service.clear_app_data(serial, app.package), f"Clear {app.package}"),
            "uninstall": (lambda: self.service.uninstall_app(serial, app.package), f"Uninstall {app.package}"),
            "disable": (lambda: self.service.disable_app(serial, app.package), f"Disable {app.package}"),
            "enable": (lambda: self.service.enable_app(serial, app.package), f"Enable {app.package}"),
            "pull_apk": (self._pull_apk, f"Pull APK {app.package}"),
        }

        if action in cmds:
            func, desc = cmds[action]
            if action == "uninstall" and not confirm_dialog(self, "Uninstall", f"Uninstall {app.package}?", "UNINSTALL"):
                return
            self.app.run_bg(func, lambda r: (self.app.log(desc, r, "ok"), self.refresh()), f"adb {desc}")

    def _pull_apk(self) -> None:
        serial = self.require_device()
        if not serial:
            return
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx >= len(self.apps):
            return
        app = self.apps[idx]
        dest = ask_save_file(self, "Save APK", initialfile=f"{app.package}.apk", defaultextension=".apk")
        if not dest:
            return
        self.app.run_bg(
            lambda: self.service.pull_apk(serial, app.package, dest),
            lambda r: self.app.log(f"Pull APK {app.package}", r, "ok"),
        )

    def _install_apk(self) -> None:
        serial = self.require_device()
        if not serial:
            return
        paths = ask_open_file(self, "Install APK", [("APK files", "*.apk"), ("All files", "*.*")])
        if not paths:
            return
        # tkinter returns a tuple if multiple files selected
        if isinstance(paths, tuple):
            path_list = list(paths)
        else:
            path_list = [paths]

        def work():
            return self.service.install_multiple(serial, path_list)

        self.app.run_bg(work, lambda r: (self.app.log("Install APKs", "\n".join(r), "ok"), self.refresh()))

    def refresh(self) -> None:
        serial = self.require_device()
        if not serial:
            self.tree.delete(*self.tree.get_children())
            return

        def work():
            return self.service.list_packages(serial)

        def done(apps):
            self.apps = apps
            self.tree.delete(*self.tree.get_children())
            for i, app in enumerate(apps):
                state = "enabled"  # Would need more info to determine
                self.tree.insert("", "end", iid=str(i), values=(app.package, app.version or "-", state))

        self.app.run_bg(work, done)


class AdbFilesTab(TabBase):
    """File browser tab."""

    def __init__(self, parent: tk.Widget, app: "MainWindow", adb: AdbService):
        super().__init__(parent, app, adb)
        self.current_path = tk.StringVar(value="/sdcard")
        self.files: list[FileInfo] = []
        self._build_ui()

    def _build_ui(self) -> None:
        bar = Toolbar(self)
        bar.pack(fill="x", pady=(0, 8))

        bar.add_button("up", "Up", self._go_up)
        bar.add_separator()

        entry = ttk.Entry(bar, textvariable=self.current_path, font=MONO_FONT)
        entry.pack(side="left", fill="x", expand=True, padx=8)
        entry.bind("<Return>", lambda e: self.refresh())

        bar.add_button("refresh", "Refresh", self.refresh)

        frame, self.tree = make_tree_widget(self, ("name", "type", "size"), (400, 80, 100))
        frame.pack(fill="both", expand=True, pady=(8, 0))

        bar2 = Toolbar(self)
        bar2.pack(fill="x", pady=(8, 0))

        bar2.add_button("pull", "Pull…", self._pull)
        bar2.add_button("push", "Push…", self._push, style="Accent.TButton")
        bar2.add_button("delete", "Delete", self._delete, style="Danger.TButton")

        self.tree.bind("<Double-1>", lambda e: self._enter_dir())

    def _go_up(self) -> None:
        path = self.current_path.get()
        parent = re.sub(r"/[^/]+/?$", "", path) or "/"
        self.current_path.set(parent)
        self.refresh()

    def _enter_dir(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx >= len(self.files):
            return
        file = self.files[idx]
        if file.is_dir:
            self.current_path.set(file.path)
            self.refresh()

    def _pull(self) -> None:
        serial = self.require_device()
        if not serial:
            return
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx >= len(self.files):
            return
        file = self.files[idx]
        if not file.is_file:
            return
        dest = ask_save_file(self, "Save File", initialfile=file.name)
        if not dest:
            return
        self.app.run_bg(
            lambda: self.service.pull_file(serial, file.path, dest),
            lambda r: self.app.log(f"Pull {file.name}", r, "ok"),
        )

    def _push(self) -> None:
        serial = self.require_device()
        if not serial:
            return
        src = ask_open_file(self, "Push File")
        if not src:
            return
        self.app.run_bg(
            lambda: self.service.push_file(serial, src, self.current_path.get()),
            lambda r: (self.app.log(f"Push {Path(src).name}", r, "ok"), self.refresh()),
        )

    def _delete(self) -> None:
        serial = self.require_device()
        if not serial:
            return
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx >= len(self.files):
            return
        file = self.files[idx]
        if not ask_yes_no(self, "Delete", f"Delete {file.path}?"):
            return
        self.app.run_bg(
            lambda: self.service.delete_file(serial, file.path),
            lambda r: (self.app.log(f"Delete {file.name}", r, "ok"), self.refresh()),
        )

    def refresh(self) -> None:
        serial = self.require_device()
        if not serial:
            self.tree.delete(*self.tree.get_children())
            return

        path = self.current_path.get()

        def work():
            return self.service.list_files(serial, path)

        def done(files):
            self.files = files
            self.tree.delete(*self.tree.get_children())
            for i, f in enumerate(files):
                self.tree.insert("", "end", iid=str(i), values=(f.name, f.type.value, f.size))

        self.app.run_bg(work, done)


class AdbShellTab(TabBase):
    """Shell tab."""

    def __init__(self, parent: tk.Widget, app: "MainWindow", adb: AdbService):
        super().__init__(parent, app, adb)
        self._build_ui()

    def _build_ui(self) -> None:
        frame, self.output = make_text_widget(self, state="disabled")
        frame.pack(fill="both", expand=True)

        self.input = ttk.Entry(self, font=MONO_FONT)
        self.input.pack(fill="x", pady=(8, 0))
        self.input.bind("<Return>", self._run_cmd)

        self.output.configure(state="normal")
        self.output.insert("end", "Type a command and press Enter, e.g.  getprop ro.product.model\n")
        self.output.configure(state="disabled")

    def _run_cmd(self, event) -> None:
        serial = self.require_device()
        if not serial:
            return
        cmd = self.input.get().strip()
        if not cmd:
            return
        self.input.delete(0, "end")

        def done(result):
            self.output.configure(state="normal")
            self.output.insert("end", f"$ {cmd}\n", "cmd")
            self.output.insert("end", result.rstrip() + "\n")
            self.output.see("end")
            self.output.configure(state="disabled")

        self.app.run_bg(
            lambda: self.service.shell(serial, cmd),
            done,
            f"adb -s {serial} shell {cmd}",
        )


class AdbLogcatTab(TabBase):
    """Logcat tab."""

    def __init__(self, parent: tk.Widget, app: "MainWindow", adb: AdbService):
        super().__init__(parent, app, adb)
        self.log_proc: Optional[subprocess.Popen] = None
        self.log_buffer: deque = deque(maxlen=20000)
        self._build_ui()

    def _build_ui(self) -> None:
        bar = Toolbar(self)
        bar.pack(fill="x", pady=(0, 8))

        self.filter_var = tk.StringVar()
        self.level_var = tk.StringVar(value="V")
        self.find_var = tk.StringVar()

        ttk.Label(bar, text="Level:", style="Mut.TLabel").pack(side="left")
        ttk.Combobox(
            bar, textvariable=self.level_var, values=list("VDIWEF"),
            width=3, state="readonly", justify="center"
        ).pack(side="left", padx=(6, 18))

        ttk.Label(bar, text="Filter:", style="Mut.TLabel").pack(side="left")
        ttk.Entry(bar, textvariable=self.filter_var, width=22).pack(side="left", padx=(6, 18))

        ttk.Label(bar, text="Find:", style="Mut.TLabel").pack(side="left")
        ttk.Entry(bar, textvariable=self.find_var, width=18).pack(side="left", padx=6)

        bar2 = Toolbar(self)
        bar2.pack(fill="x", pady=(0, 8))

        bar2.add_button("start", "Start", self._start, style="Accent.TButton")
        bar2.add_button("stop", "Stop", self._stop)
        bar2.add_button("clear", "Clear", self._clear)
        bar2.add_button("save", "Save…", self._save)

        frame, self.output = make_text_widget(self)
        frame.pack(fill="both", expand=True)

        self.output.tag_configure("E", foreground=ERR)
        self.output.tag_configure("W", foreground=WARN)

    def _start(self) -> None:
        serial = self.require_device()
        if not serial:
            return
        try:
            extra = shlex.split(self.filter_var.get())
        except ValueError as e:
            show_error(self, "Logcat filter", str(e))
            return

        self._stop()
        self.log_buffer.clear()
        self.output.delete("1.0", "end")

        cmd = [self.service.adb_path, "-s", serial, "logcat", "-v", "threadtime"] + extra
        self.log_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        )

        def reader():
            assert self.log_proc.stdout is not None
            for raw in self.log_proc.stdout:
                self.log_buffer.append(raw.decode("utf-8", "replace").rstrip())

        threading.Thread(target=reader, daemon=True).start()
        self._flush()

    def _flush(self) -> None:
        if not self.log_proc:
            return
        order = "VDIWEF"
        level_idx = order.index(self.level_var.get())
        find_text = self.find_var.get().lower()
        n = 0
        while self.log_buffer and n < 400:
            line = self.log_buffer.popleft()
            n += 1
            m = re.match(r"^\S+\s+\S+\s+\d+\s+\d+\s+([VDIWEF])\s", line)
            lvl = m.group(1) if m else "I"
            if order.index(lvl) >= level_idx and find_text in line.lower():
                self.output.insert("end", line + "\n", lvl)
        if n:
            if int(self.output.index("end-1c").split(".")[0]) > 5000:
                self.output.delete("1.0", "1500.0")
            self.output.see("end")
        self.after(120, self._flush)

    def _stop(self) -> None:
        if self.log_proc:
            self.log_proc.terminate()
            self.log_proc = None

    def _clear(self) -> None:
        self.output.delete("1.0", "end")

    def _save(self) -> None:
        path = ask_save_file(self, "Save Logcat", initialfile="logcat.txt", defaultextension=".txt")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.output.get("1.0", "end"))

    def on_hide(self) -> None:
        self._stop()
        super().on_hide()


class AdbScreenTab(TabBase):
    """Screen view tab."""

    def __init__(self, parent: tk.Widget, app: "MainWindow", adb: AdbService):
        super().__init__(parent, app, adb)
        self.screenshot_data: Optional[bytes] = None
        self.scale = 1.0
        self.live = tk.BooleanVar()
        self.busy = False
        self._build_ui()
        self._tick()

    def _build_ui(self) -> None:
        bar = Toolbar(self)
        bar.pack(fill="x", pady=(0, 6))

        bar.add_button("capture", "Capture", self._capture, style="Accent.TButton")
        ttk.Checkbutton(bar, text="Live (1.5 s)", variable=self.live).pack(side="left", padx=10)
        bar.add_button("save", "Save PNG…", self._save)

        ttk.Label(bar, text="Click screenshot to tap", style="Mut.TLabel").pack(side="right")

        # Navigation keys
        keys = Toolbar(self)
        keys.pack(fill="x", pady=(0, 8))
        for text, code in (
            ("◀ Back", 4), ("● Home", 3), ("▣ Recents", 187),
            ("Power", 26), ("Vol +", 24), ("Vol −", 25),
        ):
            keys.add_button(f"key_{code}", text, lambda c=code: self._key(c))

        self.label = ttk.Label(self, anchor="center", cursor="hand2", style="Mut.TLabel", text="Press Capture to grab the screen")
        self.label.bind("<Button-1>", self._tap)
        self.label.pack(fill="both", expand=True)

    def _capture(self) -> None:
        serial = self.require_device()
        if not serial or self.busy:
            return
        self.busy = True

        def work():
            try:
                return self.service.screenshot(serial)
            finally:
                self.app.queue_ui(lambda: setattr(self, "busy", False))

        def done(data):
            self.screenshot_data = data
            try:
                img = Image.open(io.BytesIO(data)).convert("RGB")
            except Exception:
                return
            avail_h = max(200, self.winfo_height() - 150)
            avail_w = max(200, self.winfo_width() - 24)
            scale = min(1.0, avail_h / img.height, avail_w / img.width)
            if scale < 1.0:
                size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
                img = img.resize(size, getattr(Image, "Resampling", Image).LANCZOS)
            self.scale = 1 / scale if scale < 1.0 else 1.0
            photo = ImageTk.PhotoImage(img)
            self.label.configure(image=photo, text="")
            self.label.image = photo  # Keep reference

        self.app.run_bg(work, done)

    def _tap(self, event) -> None:
        if not self.screenshot_data:
            return
        w, h = self.label.image.width(), self.label.image.height()
        x = (event.x - (self.label.winfo_width() - w) / 2) * self.scale
        y = (event.y - (self.label.winfo_height() - h) / 2) * self.scale
        if 0 <= x <= w * self.scale and 0 <= y <= h * self.scale:
            serial = self.require_device()
            if serial:
                self.app.run_bg(
                    lambda: self.service.input_tap(serial, int(x), int(y)),
                    lambda r: self.after(500, self._capture),
                )

    def _key(self, code: int) -> None:
        serial = self.require_device()
        if serial:
            self.app.run_bg(
                lambda: self.service.input_keyevent(serial, code),
                lambda r: self.after(500, self._capture),
            )

    def _save(self) -> None:
        if not self.screenshot_data:
            return
        path = ask_save_file(self, "Save Screenshot", initialfile="screenshot.png", defaultextension=".png")
        if path:
            with open(path, "wb") as f:
                f.write(self.screenshot_data)

    def _tick(self) -> None:
        if self.live.get() and self.app.mode.get() == "adb" and self.winfo_ismapped():
            self._capture()
        self.after(1500, self._tick)


# ============================================================
# Fastboot Tabs
# ============================================================

class FastbootDeviceTab(TabBase):
    """Fastboot device info tab."""

    def __init__(self, parent: tk.Widget, app: "MainWindow", fastboot: FastbootService):
        super().__init__(parent, app, fastboot)
        self._build_ui()

    def _build_ui(self) -> None:
        self.state_var = tk.StringVar(value="Bootloader state: unknown")
        ttk.Label(self, textvariable=self.state_var, style="BigBg.TLabel").pack(anchor="w", pady=(0, 8))

        bar = Toolbar(self)
        bar.pack(fill="x", pady=(0, 8))
        bar.add_button("refresh", "Refresh", self.refresh)
        bar.add_button("save", "Save report…", self._save)

        frame, self.tree = make_tree_widget(self, ("variable", "value"), (260, 500))
        frame.pack(fill="both", expand=True)

    def refresh(self) -> None:
        serial = self.require_device()
        if not serial:
            return

        def work():
            return self.service.get_variables(serial)

        def done(vars):
            self.tree.delete(*self.tree.get_children())
            for k, v in sorted(vars.variables.items()):
                self.tree.insert("", "end", values=(k, v))
            self.state_var.set(f"Bootloader: {vars.unlocked_text}")

        self.app.run_bg(work, done)

    def _save(self) -> None:
        path = ask_save_file(self, "Save Fastboot Variables", initialfile="fastboot-vars.txt", defaultextension=".txt")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            for item in self.tree.get_children():
                vals = self.tree.item(item, "values")
                f.write(f"{vals[0]}: {vals[1]}\n")


class FastbootFlashTab(TabBase):
    """Flash tab."""

    def __init__(self, parent: tk.Widget, app: "MainWindow", fastboot: FastbootService, presets: PresetService):
        super().__init__(parent, app, fastboot)
        self.presets = presets
        self._build_ui()

    def _build_ui(self) -> None:
        # Preset bar
        pbar = ttk.Frame(self)
        pbar.pack(anchor="w", pady=(0, 12))

        ttk.Label(pbar, text="Preset", style="Mut.TLabel").pack(side="left")
        self.preset_combo = ttk.Combobox(pbar, values=[], width=22, state="readonly")
        self.preset_combo.pack(side="left", padx=8)
        self._update_preset_list()

        ttk.Button(pbar, text="Load", command=self._load_preset).pack(side="left", padx=2)
        ttk.Button(pbar, text="Save current…", command=self._save_preset).pack(side="left", padx=2)
        ttk.Button(pbar, text="Delete", style="Danger.TButton", command=self._delete_preset).pack(side="left", padx=2)

        # Flash options
        grid = ttk.Frame(self)
        grid.pack(anchor="w", pady=(0, 8))

        self.partition_var = tk.StringVar()
        self.image_var = tk.StringVar()
        self.slot_var = tk.StringVar(value="active")
        self.verity_var = tk.BooleanVar()
        self.verification_var = tk.BooleanVar()

        ttk.Label(grid, text="Partition").grid(row=0, column=0, sticky="w", pady=6)
        self.partition_combo = ttk.Combobox(grid, textvariable=self.partition_var, width=28)
        self.partition_combo.grid(row=0, column=1, padx=10, sticky="w")

        ttk.Label(grid, text="Image").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(grid, textvariable=self.image_var, width=44).grid(row=1, column=1, padx=10)
        ttk.Button(grid, text="Browse…", command=self._browse_image).grid(row=1, column=2)

        ttk.Label(grid, text="Slot").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Combobox(grid, textvariable=self.slot_var, values=["active", "a", "b", "all"], state="readonly", width=10).grid(row=2, column=1, padx=10, sticky="w")

        ttk.Checkbutton(self, text="--disable-verity", variable=self.verity_var).pack(anchor="w")
        ttk.Checkbutton(self, text="--disable-verification", variable=self.verification_var).pack(anchor="w")

        # Progress
        self.progress = ttk.Progressbar(self, mode="determinate", maximum=100, length=320)
        self.progress_var = tk.StringVar()
        self.progress_label = ttk.Label(self, textvariable=self.progress_var, style="Mut.TLabel")

        # Flash button
        ttk.Button(self, text="Flash image", style="Accent.TButton", command=self._flash).pack(anchor="w", pady=14)

    def _update_preset_list(self) -> None:
        names = self.presets.get_names()
        self.preset_combo["values"] = names

    def _load_preset(self) -> None:
        name = self.preset_combo.get()
        if not name:
            return
        preset = self.presets.get(name)
        if preset:
            self.partition_var.set(preset.partition)
            self.slot_var.set(preset.slot)
            self.image_var.set(preset.image)
            self.verity_var.set(preset.verity)
            self.verification_var.set(preset.verification)

    def _save_preset(self) -> None:
        name = ask_string(self, "Save preset", "Preset name:")
        if not name:
            return
        preset = FlashPreset(
            name=name,
            partition=self.partition_var.get(),
            slot=self.slot_var.get(),
            image=self.image_var.get(),
            verity=self.verity_var.get(),
            verification=self.verification_var.get(),
        )
        self.presets.add(preset)
        self._update_preset_list()
        self.preset_combo.set(name)

    def _delete_preset(self) -> None:
        name = self.preset_combo.get()
        if name and self.presets.delete(name):
            self._update_preset_list()
            self.preset_combo.set("")

    def _browse_image(self) -> None:
        path = ask_open_file(self, "Select Image", [("Images", "*.img *.bin"), ("All files", "*.*")])
        if path:
            self.image_var.set(path)
            stem = Path(path).stem
            if validate_partition_name(stem):
                self.partition_var.set(stem)

    def _flash(self) -> None:
        serial = self.require_device()
        if not serial:
            return
        partition = self.partition_var.get().strip()
        image = self.image_var.get().strip()
        if not validate_partition_name(partition) or not image:
            show_error(self, "Flash", "Enter a valid partition name and choose an image.")
            return
        if not confirm_dialog(self, "Flash image", f"Write {image} to {partition}. A wrong image can brick the device.", "FLASH"):
            return

        options = FlashOptions(
            partition=partition,
            image_path=image,
            slot=self.slot_var.get(),
            disable_verity=self.verity_var.get(),
            disable_verification=self.verification_var.get(),
        )

        self.progress.configure(value=0)
        self.progress_var.set("Flashing… 0%")
        self.progress.pack(anchor="w", pady=(10, 2))
        self.progress_label.pack(anchor="w")

        def progress(pct: int) -> None:
            self.app.queue_ui(lambda: (self.progress.configure(value=pct), self.progress_var.set(f"Flashing… {pct}%")))

        def done(result):
            self.app.queue_ui(lambda: (self.progress.pack_forget(), self.progress_label.pack_forget()))
            self.app.log("Flash", result, "ok")

        self.app.run_bg(
            lambda: self.service.flash(serial, options, progress),
            done,
            f"fastboot -s {serial} {' '.join(options.to_fastboot_args())}",
        )

    def refresh(self) -> None:
        serial = self.require_device()
        if not serial:
            return

        def work():
            return self.service.get_variables(serial)

        def done(vars):
            names = sorted({p.base_name for p in vars.partitions})
            fallback = ["boot", "init_boot", "vendor_boot", "dtbo", "vbmeta", "recovery", "system", "vendor", "userdata"]
            self.partition_combo["values"] = names or fallback

        self.app.run_bg(work, done)


class FastbootPartitionsTab(TabBase):
    """Partitions tab."""

    def __init__(self, parent: tk.Widget, app: "MainWindow", fastboot: FastbootService):
        super().__init__(parent, app, fastboot)
        self.partitions: list[Partition] = []
        self._build_ui()

    def _build_ui(self) -> None:
        frame, self.tree = make_tree_widget(self, ("partition", "size", "type"), (320, 120, 100))
        frame.pack(fill="both", expand=True, pady=(0, 8))

        bar = Toolbar(self)
        bar.pack(fill="x")
        bar.add_button("flash", "Flash selected…", self._flash_selected)
        bar.add_button("erase", "Erase selected", self._erase_selected, style="Danger.TButton")

    def _flash_selected(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx >= len(self.partitions):
            return
        p = self.partitions[idx]
        self.app.nb["fb"].select(1)  # Switch to flash tab
        self.app.flash_tab.partition_var.set(p.base_name)

    def _erase_selected(self) -> None:
        serial = self.require_device()
        if not serial:
            return
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx >= len(self.partitions):
            return
        p = self.partitions[idx]
        if confirm_dialog(self, "Erase partition", f"fastboot erase {p.name} - data on it is lost.", "ERASE"):
            self.app.run_bg(
                lambda: self.service.erase_partition(serial, p.name),
                lambda r: (self.app.log(f"Erase {p.name}", r, "ok"), self.refresh()),
            )

    def refresh(self) -> None:
        serial = self.require_device()
        if not serial:
            self.tree.delete(*self.tree.get_children())
            return

        def work():
            return self.service.get_variables(serial)

        def done(vars):
            self.partitions = vars.partitions
            self.tree.delete(*self.tree.get_children())
            for i, p in enumerate(self.partitions):
                self.tree.insert("", "end", iid=str(i), values=(p.name, p.human_size(), p.type.value))

        self.app.run_bg(work, done)


class FastbootBootloaderTab(TabBase):
    """Bootloader tab."""

    def __init__(self, parent: tk.Widget, app: "MainWindow", fastboot: FastbootService):
        super().__init__(parent, app, fastboot)
        self._build_ui()

    def _build_ui(self) -> None:
        # Dangerous actions
        actions = [
            ("Unlock bootloader", ["flashing", "unlock"], "UNLOCK", "Unlocking wipes user data and weakens boot security."),
            ("Lock bootloader", ["flashing", "lock"], "LOCK", "Locking with a modified system can brick the device."),
            ("Wipe data (-w)", ["-w"], "WIPE", "This erases userdata and cache."),
        ]

        for text, args, word, msg in actions:
            ttk.Button(
                self, text=text, style="Danger.TButton", width=26,
                command=lambda a=args, w=word, m=msg: self._danger(a, w, m)
            ).pack(anchor="w", pady=5)

        # Slot selection
        ttk.Label(self, text="Active slot", style="Mut.TLabel").pack(anchor="w", pady=(16, 4))
        slot_frame = ttk.Frame(self)
        slot_frame.pack(anchor="w")
        for slot in ("a", "b"):
            ttk.Button(slot_frame, text=f"Set slot {slot}", command=lambda s=slot: self._set_slot(s)).pack(side="left", padx=(0, 6))

    def _danger(self, args: list[str], word: str, msg: str) -> None:
        serial = self.require_device()
        if not serial:
            return
        if confirm_dialog(self, "Confirm", msg, word):
            self.app.run_bg(
                lambda: self.service.run(serial, args),
                lambda r: (self.app.log("Bootloader", r, "ok"), setattr(self.service, "_cached_vars", None)),
            )

    def _set_slot(self, slot: str) -> None:
        serial = self.require_device()
        if serial:
            self.app.run_bg(
                lambda: self.service.set_active_slot(serial, slot),
                lambda r: self.app.log(f"Set active slot {slot}", r, "ok"),
            )


class FastbootRebootTab(TabBase):
    """Reboot tab."""

    def __init__(self, parent: tk.Widget, app: "MainWindow", fastboot: FastbootService):
        super().__init__(parent, app, fastboot)
        self._build_ui()

    def _build_ui(self) -> None:
        for text, target in (
            ("Reboot to system", ""),
            ("Reboot to bootloader", "bootloader"),
            ("Reboot to recovery", "recovery"),
            ("Reboot to fastbootd", "fastboot"),
        ):
            ttk.Button(
                self, text=text, width=26,
                command=lambda t=target: self._reboot(t)
            ).pack(anchor="w", pady=5)

    def _reboot(self, target: str) -> None:
        serial = self.require_device()
        if serial:
            self.app.run_bg(
                lambda: self.service.reboot(serial, target),
                lambda r: self.app.log(f"Reboot {target or 'system'}", r, "ok"),
            )


# Import subprocess at the top for LogcatTab
import subprocess
