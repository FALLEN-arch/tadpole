"""Main application window for Tadpole."""
from __future__ import annotations

import queue
import shlex
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Any, Callable, Optional

from tkinterdnd2 import DND_FILES, TkinterDnD  # required: drag and drop is a core feature

from ..models.device import Device, DeviceState
from ..models.flash import FlashPreset
from ..services.adb_service import AdbService, AdbError
from ..services.fastboot_service import FastbootService, FastbootError
from ..services.preset_service import PresetService
from ..services.config_service import ConfigService
from ..utils.theme import (
    BG, PANEL, PANEL2, LINE, TX, MUT, ACC, ACCS, OK, WARN, ERR, TERM, ON_ACC,
    apply_dark_theme,
)
from ..utils.threading import run_in_background, get_task_queue
from .widgets import Toolbar, StatusPill, make_text_widget
from .tabs import (
    AdbOverviewTab,
    AdbAppsTab,
    AdbFilesTab,
    AdbShellTab,
    AdbLogcatTab,
    AdbScreenTab,
    FastbootDeviceTab,
    FastbootFlashTab,
    FastbootPartitionsTab,
    FastbootBootloaderTab,
    FastbootRebootTab,
)

BaseTk = TkinterDnD.Tk


class MainWindow(BaseTk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title("Tadpole")
        self.geometry("1100x740")
        self.minsize(760, 520)

        # Services
        self.adb = AdbService()
        self.fastboot = FastbootService()

        # Config
        self.config_dir = Path.home() / ".tadpole"
        if not self.config_dir.exists() and (Path.home() / ".adb-studio").is_dir():
            self.config_dir = Path.home() / ".adb-studio"
        self.config = ConfigService(self.config_dir)
        self.presets = PresetService(self.config_dir)

        # State
        self.mode = tk.StringVar(value="adb")
        self.devices: list[Device] = []
        self.current_serial: Optional[str] = None
        self._device_map: dict[str, str] = {}  # display -> serial
        self._last_device_sig: Optional[tuple] = None

        # Terminal
        self.cmd_history: list[str] = []
        self.cmd_history_idx = 0

        # UI setup
        apply_dark_theme(self)
        self._build_ui()
        self._setup_dnd()

        # Task queue for background operations
        self._ui_queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self.after(50, self._pump_ui_queue)

        # Device polling
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll_devices()
        self._poll_loop()

    # ============================================================
    # UI Construction
    # ============================================================

    def _build_ui(self) -> None:
        # Top bar
        top = ttk.Frame(self, style="Top.TFrame", padding=(14, 10))
        top.pack(fill="x")

        ttk.Label(top, text="Tadpole", style="Top.TLabel").pack(side="left", padx=(0, 16))

        # Mode switch
        for text, val in (("ADB", "adb"), ("Fastboot", "fb")):
            ttk.Radiobutton(
                top, text=text, value=val, variable=self.mode,
                style="Toolbutton", command=self._switch_mode
            ).pack(side="left", padx=2)

        # Device selector
        self.device_combo = ttk.Combobox(top, state="readonly", width=44)
        self.device_combo.pack(side="left", padx=14)
        self.device_combo.bind("<<ComboboxSelected>>", lambda e: self._on_device_selected())

        Toolbar(top).add_button("refresh", "Refresh", self._poll_devices).pack(side="left")

        self.status_pill = StatusPill(top)
        self.status_pill.pack(side="left", padx=14)

        # WiFi buttons (ADB mode only)
        self.wifi_frame = ttk.Frame(top, style="Top.TFrame")
        self.wifi_frame.pack(side="right")
        Toolbar(self.wifi_frame).add_button("connect", "Connect…", self._connect_wifi).pack(side="left", padx=3)
        Toolbar(self.wifi_frame).add_button("pair", "Pair…", self._pair_wifi).pack(side="left", padx=3)
        Toolbar(self.wifi_frame).add_button("restart", "Restart server", self._restart_adb).pack(side="left", padx=3)

        # Main paned window
        paned = ttk.PanedWindow(self, orient="vertical")
        paned.pack(fill="both", expand=True, padx=10, pady=10)

        # Body (tabs)
        self.body = ttk.Frame(paned)
        paned.add(self.body, weight=4)

        # Terminal dock
        dock = ttk.Frame(paned)
        paned.add(dock, weight=1)

        dock_header = ttk.Frame(dock)
        dock_header.pack(fill="x", pady=(0, 4))
        ttk.Label(dock_header, text="TERMINAL", style="Mut.TLabel").pack(side="left")
        Toolbar(dock_header).add_button("clear", "Clear", self._clear_terminal).pack(side="right")

        dock_frame, self.terminal = make_text_widget(dock, height=8, state="disabled")
        dock_frame.pack(fill="both", expand=True)

        self.cmd_entry = ttk.Entry(dock, font=("DejaVu Sans Mono", 10))
        self.cmd_entry.pack(fill="x", pady=(6, 0))
        self.cmd_entry.bind("<Return>", self._run_terminal_cmd)
        self.cmd_entry.bind("<Up>", lambda e: self._nav_history(-1))
        self.cmd_entry.bind("<Down>", lambda e: self._nav_history(1))

        # Fastboot hint
        self.fb_hint = ttk.Label(
            self.body, style="Mut.TLabel", wraplength=900, justify="left",
            text="No fastboot device found. Boot the phone into the bootloader "
                 "(power off, then hold Vol− + Power), connect USB, then press Refresh. "
                 "From the ADB tab you can also use Overview ▸ Bootloader."
        )

        # Tab navigation
        self.nb = {
            "adb": self._create_adb_tabs(),
            "fb": self._create_fastboot_tabs(),
        }

        self._switch_mode()
        self.log("ready", "Pick a device above. Terminal accepts adb / fastboot commands.")

    def _create_adb_tabs(self):
        """Create ADB mode tabs."""
        nav = self._create_nav("adb")
        tabs = [
            ("◈  Overview", lambda p: AdbOverviewTab(p, self, self.adb)),
            ("▦  Apps", lambda p: AdbAppsTab(p, self, self.adb)),
            ("▤  Files", lambda p: AdbFilesTab(p, self, self.adb)),
            ("❯  Shell", lambda p: AdbShellTab(p, self, self.adb)),
            ("☰  Logcat", lambda p: AdbLogcatTab(p, self, self.adb)),
            ("▣  Screen", lambda p: AdbScreenTab(p, self, self.adb)),
        ]
        for title, factory in tabs:
            frame = ttk.Frame(nav, padding=14)
            tab = factory(frame)
            frame.on_show = tab.on_show
            frame.on_hide = tab.on_hide
            nav.add(frame, text=title)
        return nav

    def _create_fastboot_tabs(self):
        """Create Fastboot mode tabs."""
        nav = self._create_nav("fb")
        tabs = [
            ("◈  Device", lambda p: FastbootDeviceTab(p, self, self.fastboot)),
            ("⚡  Flash", lambda p: FastbootFlashTab(p, self, self.fastboot, self.presets)),
            ("▤  Partitions", lambda p: FastbootPartitionsTab(p, self, self.fastboot)),
            ("⚿  Bootloader", lambda p: FastbootBootloaderTab(p, self, self.fastboot)),
            ("⟳  Reboot", lambda p: FastbootRebootTab(p, self, self.fastboot)),
        ]
        for title, factory in tabs:
            frame = ttk.Frame(nav, padding=14)
            tab = factory(frame)
            frame.on_show = tab.on_show
            frame.on_hide = tab.on_hide
            nav.add(frame, text=title)
        return nav

    def _create_nav(self, mode: str):
        """Create a SideNav for the given mode."""
        nav = self._SideNav(self.body, on_change=self._refresh_current_tab)
        return nav

    class _SideNav(ttk.Frame):
        """Internal SideNav with on_change callback."""

        def __init__(self, parent, on_change: Callable[[], None]):
            super().__init__(parent)
            self._on_change = on_change
            self._tabs: list[tuple[ttk.Frame, ttk.Button]] = []
            self._current: Optional[int] = None

            self.side = ttk.Frame(self, style="Side.TFrame", padding=(8, 12))
            self.side.pack(side="left", fill="y")

            right = ttk.Frame(self)
            right.pack(side="left", fill="both", expand=True, padx=(16, 0))

            self.head = ttk.Label(right, style="Head.TLabel")
            self.head.pack(anchor="w", pady=(2, 10))

            self.stage = ttk.Frame(right)
            self.stage.pack(fill="both", expand=True)

        def add(self, frame: ttk.Frame, text: str) -> None:
            idx = len(self._tabs)
            btn = ttk.Button(
                self.side, text=text, style="Nav.Toolbutton", width=18,
                command=lambda: self.select(idx)
            )
            btn.pack(fill="x", pady=1)
            self._tabs.append((frame, btn))
            if self._current is None:
                self.select(idx, notify=False)

        def select(self, idx: Optional[int] = None, notify: bool = True) -> str:
            if idx is None:
                return str(self._tabs[self._current][0]) if self._current is not None else ""

            for n, (frame, btn) in enumerate(self._tabs):
                if n == idx:
                    frame.pack(in_=self.stage, fill="both", expand=True)
                    if hasattr(frame, "on_show"):
                        frame.on_show()
                    btn.state(["selected"])
                    self.head.configure(text=btn.cget("text").split(None, 1)[-1])
                else:
                    frame.pack_forget()
                    if hasattr(frame, "on_hide"):
                        frame.on_hide()
                    btn.state(["!selected"])
            self._current = idx
            if notify and self._on_change:
                self._on_change()
            return str(self._tabs[idx][0])

        def pack(self, **kwargs):
            super().pack(**kwargs)

        def pack_forget(self):
            super().pack_forget()

    # Store references to flash tab for cross-tab navigation
    @property
    def flash_tab(self):
        """Get the FastbootFlashTab instance."""
        nav = self.nb["fb"]
        if hasattr(nav, "_tabs") and len(nav._tabs) > 1:
            frame = nav._tabs[1][0]
            if hasattr(frame, "on_show"):
                # Find the tab instance
                for child in frame.winfo_children():
                    if hasattr(child, "_flash"):
                        return child
        return None

    # ============================================================
    # Mode/Device Management
    # ============================================================

    def _switch_mode(self) -> None:
        """Switch between ADB and Fastboot modes."""
        # Stop any running logcat
        for nav in self.nb.values():
            if hasattr(nav, "_tabs"):
                for frame, _ in nav._tabs:
                    if hasattr(frame, "on_hide"):
                        frame.on_hide()

        for k, nav in self.nb.items():
            nav.pack_forget()

        mode = self.mode.get()
        self.nb[mode].pack(fill="both", expand=True)

        if mode == "adb":
            self.wifi_frame.pack(side="right")
            self.fb_hint.pack_forget()
        else:
            self.wifi_frame.pack_forget()
            self._update_fb_hint()

        self.cmd_entry.delete(0, "end")
        self._last_device_sig = None
        self._poll_devices()

    def _update_fb_hint(self) -> None:
        if self.mode.get() == "fb" and not self.current_serial:
            self.fb_hint.pack(side="top", fill="x", pady=(0, 6), before=self.nb["fb"])
        else:
            self.fb_hint.pack_forget()

    def _on_device_selected(self) -> None:
        """Handle device selection change."""
        display = self.device_combo.get()
        self.current_serial = self._device_map.get(display)
        self._update_fb_hint()
        self._refresh_current_tab()

    def _refresh_current_tab(self) -> None:
        """Refresh the currently visible tab."""
        mode = self.mode.get()
        nav = self.nb[mode]
        if hasattr(nav, "_current") and nav._current is not None:
            frame = nav._tabs[nav._current][0]
            if hasattr(frame, "on_show"):
                frame.on_show()

    @property
    def current_serial(self) -> Optional[str]:
        return self._current_serial

    @current_serial.setter
    def current_serial(self, value: Optional[str]) -> None:
        self._current_serial = value

    # ============================================================
    # Device Polling
    # ============================================================

    def _poll_devices(self) -> None:
        """Poll for connected devices."""
        mode = self.mode.get()

        def work():
            if mode == "adb":
                return self.adb.list_devices()
            else:
                fb_devices = self.fastboot.list_devices()
                return [Device(
                    serial=d["serial"],
                    state=DeviceState.FASTBOOT if d["state"] == "fastboot" else DeviceState.UNKNOWN,
                ) for d in fb_devices]

        def done(devices: list[Device]):
            if mode != self.mode.get():
                return

            self.devices = devices
            sig = tuple((d.serial, d.state.value) for d in devices)
            if sig == self._last_device_sig:
                return
            self._last_device_sig = sig

            self._device_map = {d.display_name: d.serial for d in devices}
            ready = [d for d in devices if d.is_ready]

            self.status_pill.set_ready(len(ready))

            current = self.device_combo.get()
            self.device_combo["values"] = list(self._device_map)
            if current in self._device_map:
                self.device_combo.set(current)
            elif self._device_map:
                self.device_combo.set(next(iter(self._device_map)))
                self.current_serial = next(iter(self._device_map.values()))
            else:
                self.device_combo.set("")
                self.current_serial = None

            self._update_fb_hint()
            self._refresh_current_tab()

        run_in_background(work, done)

    def _poll_loop(self) -> None:
        """Periodic device polling."""
        self._poll_devices()
        self.after(4000, self._poll_loop)

    def _poll_devices_now(self) -> None:
        """Manual refresh button."""
        self._last_device_sig = None
        self._poll_devices()

    # ============================================================
    # WiFi Actions
    # ============================================================

    def _connect_wifi(self) -> None:
        addr = self._ask_string("Connect", "Device address (ip:port):")
        if addr:
            self.run_bg(
                lambda: self.adb.connect(addr.strip()),
                lambda r: (self.log("adb connect", r, "ok"), self._poll_devices()),
                f"adb connect {addr}",
            )

    def _pair_wifi(self) -> None:
        addr = self._ask_string("Pair", "Pairing address (ip:port):")
        code = addr and self._ask_string("Pair", "Pairing code:")
        if addr and code:
            self.run_bg(
                lambda: self.adb.pair(addr.strip(), code.strip()),
                lambda r: self.log("adb pair", r, "ok"),
                f"adb pair {addr} ******",
            )

    def _restart_adb(self) -> None:
        self.run_bg(
            lambda: (self.adb.run(None, ["kill-server"]), self.adb.run(None, ["start-server"])),
            lambda r: (self.log("adb restart", r, "ok"), self._poll_devices()),
            "adb kill-server && adb start-server",
        )

    # ============================================================
    # Terminal
    # ============================================================

    def _clear_terminal(self) -> None:
        self.terminal.configure(state="normal")
        self.terminal.delete("1.0", "end")
        self.terminal.configure(state="disabled")

    def _run_terminal_cmd(self, event) -> None:
        raw = self.cmd_entry.get().strip()
        if not raw:
            return

        self.cmd_history.append(raw)
        self.cmd_history_idx = len(self.cmd_history)
        self.cmd_entry.delete(0, "end")

        try:
            args = shlex.split(raw)
        except ValueError as e:
            self.log(raw, str(e), "err")
            return

        # Strip leading adb/fastboot
        if args and args[0] in ("adb", "fastboot"):
            args = args[1:]

        # Strip -s serial
        if len(args) > 1 and args[0] == "-s":
            args = args[2:]

        if not args:
            return

        serial = self.current_serial
        if not serial:
            self.log("error", "No device selected", "warn")
            return

        is_fastboot = self.mode.get() == "fb"
        service = self.fastboot if is_fastboot else self.adb
        prefix = "fastboot" if is_fastboot else "adb"

        def run_cmd():
            if is_fastboot:
                return service.run(serial, args)
            else:
                return service.run(serial, args)

        self.run_bg(
            run_cmd,
            lambda r: self.log(f"{prefix} {' '.join(args)}", r, "ok"),
            f"{prefix} -s {serial} {' '.join(args)}",
        )

    def _nav_history(self, delta: int) -> str:
        if not self.cmd_history:
            return "break"
        self.cmd_history_idx = max(0, min(len(self.cmd_history), self.cmd_history_idx + delta))
        self.cmd_entry.delete(0, "end")
        if self.cmd_history_idx < len(self.cmd_history):
            self.cmd_entry.insert(0, self.cmd_history[self.cmd_history_idx])
        return "break"

    # ============================================================
    # Drag and Drop
    # ============================================================

    def _setup_dnd(self) -> None:
        def register(widget):
            try:
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass
            for child in widget.winfo_children():
                register(child)

        register(self)

    def _on_drop(self, event) -> None:
        files = list(self.tk.splitlist(event.data))
        if self.mode.get() == "adb":
            apks = [p for p in files if p.lower().endswith(".apk")]
            if apks:
                self._install_apks(apks)
            else:
                self.log("drop", "In ADB mode, drop .apk files to install them.", "warn")
        else:
            imgs = [p for p in files if p.lower().endswith((".img", ".bin"))]
            if imgs:
                # Navigate to flash tab and set image
                if hasattr(self.nb["fb"], "_tabs") and len(self.nb["fb"]._tabs) > 1:
                    frame = self.nb["fb"]._tabs[1][0]
                    for child in frame.winfo_children():
                        if hasattr(child, "image_var"):
                            child.image_var.set(imgs[0])
                            stem = Path(imgs[0]).stem
                            if stem and validate_partition_name(stem):
                                child.partition_var.set(stem)
                            self.nb["fb"].select(1)
                            self.log("drop", f"Loaded {imgs[0]} into Flash.", "ok")
                            return
            self.log("drop", "In Fastboot mode, drop an .img file to prepare a flash.", "warn")

    def _install_apks(self, paths: list[str]) -> None:
        serial = self.current_serial
        if not serial:
            return

        def work():
            return self.adb.install_multiple(serial, paths)

        self.run_bg(work, lambda r: self.log("Install APKs", "\n".join(r), "ok"))

    # ============================================================
    # Background Task Helpers
    # ============================================================

    def run_bg(
        self,
        func: Callable[[], Any],
        on_done: Optional[Callable[[Any], None]] = None,
        log_cmd: Optional[str] = None,
    ) -> None:
        """Run a function in background and call on_done on UI thread."""
        def work():
            try:
                result = func()
                error = None
            except Exception as e:
                result = None
                error = e

            def finish():
                if log_cmd:
                    if error:
                        self.log(log_cmd, str(error), "err")
                    elif result:
                        self.log(log_cmd, str(result), "ok")
                    else:
                        self.log(log_cmd, "OK", "ok")
                elif error:
                    self.log("error", str(error), "err")

                if on_done and not error:
                    on_done(result)

            self._ui_queue.put(finish)

        threading.Thread(target=work, daemon=True).start()

    def queue_ui(self, func: Callable[[], None]) -> None:
        """Queue a function to run on the UI thread."""
        self._ui_queue.put(func)

    def _pump_ui_queue(self) -> None:
        """Process UI queue."""
        while True:
            try:
                func = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                func()
            except Exception:
                pass  # Don't let UI callback errors break the pump
        self.after(50, self._pump_ui_queue)

    def log(self, cmd: str, out: str = "", tag: str = "") -> None:
        """Log to terminal."""
        self.terminal.configure(state="normal")
        self.terminal.insert("end", f"$ {cmd}\n", "cmd")
        if out:
            self.terminal.insert("end", out.rstrip() + "\n", tag)
        self.terminal.see("end")
        self.terminal.configure(state="disabled")

    def _ask_string(self, title: str, prompt: str) -> Optional[str]:
        from tkinter import simpledialog
        return simpledialog.askstring(title, prompt, parent=self)

    def _on_close(self) -> None:
        # Stop any running logcat
        for nav in self.nb.values():
            if hasattr(nav, "_tabs"):
                for frame, _ in nav._tabs:
                    if hasattr(frame, "on_hide"):
                        frame.on_hide()

        # Shutdown task queue
        get_task_queue().shutdown(wait=False)
        self.destroy()


def main() -> None:
    try:
        MainWindow().mainloop()
    except tk.TclError as e:
        raise SystemExit(f"Cannot open a window: {e}\nMake sure a graphical session is running (is $DISPLAY set?).")


if __name__ == "__main__":
    main()
