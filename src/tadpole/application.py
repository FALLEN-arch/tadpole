"""Tadpole GTK4 Application - Main entry point."""
from __future__ import annotations

import sys
from pathlib import Path
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Gio', '2.0')
gi.require_version('GLib', '2.0')

from gi.repository import Gtk, Adw, Gio, GLib

from .services import AdbService, FastbootService, PresetService, ConfigService
from .models import Device, DeviceState


class TadpoleApplication(Adw.Application):
    """Main application class."""

    def __init__(self):
        super().__init__(
            application_id='com.fallen-arch.Tadpole',
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE | Gio.ApplicationFlags.HANDLES_OPEN,
        )
        self._window = None
        self._services_initialized = False

        # Services (lazy init)
        self._adb_service = None
        self._fastboot_service = None
        self._preset_service = None
        self._config_service = None

        # State
        self._devices = []
        self._current_serial = None
        self._mode = "adb"  # "adb" or "fastboot"

    def do_startup(self):
        """Called on application startup."""
        Adw.Application.do_startup(self)

        # Initialize services
        self._init_services()

        # Set up actions
        self._setup_actions()

        # Load UI resources
        self._load_resources()

    def _init_services(self):
        """Initialize backend services."""
        if self._services_initialized:
            return

        config_dir = Path(GLib.get_user_config_dir()) / "tadpole"
        self._config_service = ConfigService(config_dir)
        self._preset_service = PresetService(config_dir)

        try:
            self._adb_service = AdbService()
        except Exception as e:
            print(f"Warning: ADB service unavailable: {e}")

        try:
            self._fastboot_service = FastbootService()
        except Exception as e:
            print(f"Warning: Fastboot service unavailable: {e}")

        self._services_initialized = True

    def _setup_actions(self):
        """Set up global application actions."""
        # Quit action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda a, p: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Ctrl>Q"])

        # About action
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

        # Preferences action (placeholder)
        prefs_action = Gio.SimpleAction.new("preferences", None)
        prefs_action.connect("activate", self._on_preferences)
        self.add_action(prefs_action)
        self.set_accels_for_action("app.preferences", ["<Ctrl>comma"])

        # Mode switch actions
        for mode in ["adb", "fastboot"]:
            action = Gio.SimpleAction.new_stateful(
                f"mode-{mode}",
                GLib.VariantType.new("s"),
                GLib.Variant.new_string(self._mode)
            )
            action.connect("change-state", self._on_mode_change, mode)
            self.add_action(action)

        # Refresh devices action
        refresh_action = Gio.SimpleAction.new("refresh", None)
        refresh_action.connect("activate", lambda a, p: self._refresh_devices())
        self.add_action(refresh_action)
        self.set_accels_for_action("app.refresh", ["F5"])

    def _load_resources(self):
        """Load GResource bundles (for UI files, icons, etc.)."""
        # Could load compiled resources here if using gresource
        pass

    def do_activate(self):
        """Called when application is activated."""
        if not self._window:
            self._window = TadpoleWindow(self)
        self._window.present()

    def do_command_line(self, command_line):
        """Handle command line arguments."""
        options = command_line.get_options_dict()
        # Handle any CLI options here
        self.activate()
        return 0

    # Properties for accessing services
    @property
    def adb_service(self):
        return self._adb_service

    @property
    def fastboot_service(self):
        return self._fastboot_service

    @property
    def preset_service(self):
        return self._preset_service

    @property
    def config_service(self):
        return self._config_service

    @property
    def devices(self):
        return self._devices

    @property
    def current_serial(self):
        return self._current_serial

    @current_serial.setter
    def current_serial(self, value):
        self._current_serial = value
        # Notify UI
        if self._window:
            self._window.on_device_changed(value)

    @property
    def mode(self):
        return self._mode

    # Callbacks
    def _on_about(self, action, param):
        """Show about dialog."""
        if self._window:
            about = Adw.AboutWindow(
                transient_for=self._window,
                application_name="Tadpole",
                application_icon="com.fallen-arch.Tadpole",
                version="1.0.0",
                developers=["fallen-arch"],
                license_type=Gtk.License.MIT_X11,
                website="https://github.com/FALLEN-arch/tadpole",
                issue_url="https://github.com/FALLEN-arch/tadpole/issues",
                comments="Native Linux GUI for adb and fastboot",
            )
            about.present()

    def _on_preferences(self, action, param):
        """Show preferences dialog (placeholder)."""
        # TODO: Implement preferences dialog
        pass

    def _on_mode_change(self, action, value, mode):
        """Handle mode change from action."""
        if value.get_string() == mode:
            self._mode = mode
            if self._window:
                self._window.on_mode_changed(mode)
            self._refresh_devices()

    def _refresh_devices(self):
        """Refresh device list."""
        if self._mode == "adb" and self._adb_service:
            self._refresh_adb_devices()
        elif self._mode == "fastboot" and self._fastboot_service:
            self._refresh_fastboot_devices()

    def _refresh_adb_devices(self):
        """Refresh ADB devices in background."""

        def task_func(task, source_object, cancellable):
            try:
                devices = self._adb_service.list_devices()
                task.return_value(devices)
            except Exception as e:
                task.return_error(e)

        def task_done(source_object, result):
            try:
                devices = result.propagate_value()
                self._devices = devices
                if self._window:
                    self._window.update_device_list(devices)
            except Exception as e:
                print(f"Error refreshing devices: {e}")

        task = Gio.Task.new(self, None, task_done)
        task.run_in_thread(task_func)

    def _refresh_fastboot_devices(self):
        """Refresh Fastboot devices in background."""

        def task_func(task, source_object, cancellable):
            try:
                fb_devices = self._fastboot_service.list_devices()
                devices = [
                    Device(
                        serial=d["serial"],
                        state=DeviceState.FASTBOOT if d["state"] == "fastboot" else DeviceState.UNKNOWN,
                    )
                    for d in fb_devices
                ]
                task.return_value(devices)
            except Exception as e:
                task.return_error(e)

        def task_done(source_object, result):
            try:
                devices = result.propagate_value()
                self._devices = devices
                if self._window:
                    self._window.update_device_list(devices)
            except Exception as e:
                print(f"Error refreshing fastboot devices: {e}")

        task = Gio.Task.new(self, None, task_done)
        task.run_in_thread(task_func)


class TadpoleWindow(Adw.ApplicationWindow):
    """Main application window."""

    def __init__(self, app: TadpoleApplication):
        super().__init__(application=app)
        self._app = app

        self.set_default_size(1100, 740)
        self.set_title("Tadpole")

        # Build UI
        self._build_ui()

        # Initial device refresh
        self._app._refresh_devices()

    def _build_ui(self):
        """Build the main window UI."""
        # Main layout: NavigationView for sidebar + content
        self._nav_view = Adw.NavigationView()
        self.set_content(self._nav_view)

        # Create sidebar navigation page
        sidebar_page = self._create_sidebar_page()
        self._nav_view.push_by_tag("sidebar", sidebar_page)

        # Create content stack
        self._content_stack = Adw.ViewStack()
        self._content_stack.set_vexpand(True)
        self._content_stack.set_hexpand(True)

        # We'll push content pages as needed
        # For now, show a placeholder
        self._show_placeholder()

        # Add toolbar
        self._add_toolbar()

    def _add_toolbar(self):
        """Add toolbar with title and actions."""
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.Label(label="Tadpole"))

        # Mode selector in header
        self._header_mode = Adw.ComboRow()
        self._header_mode.set_model(Gtk.StringList.new(["ADB", "Fastboot"]))
        self._header_mode.set_selected(0 if self._app._mode == "adb" else 1)
        self._header_mode.connect("notify::selected", self._on_header_mode_changed)
        header.pack_start(self._header_mode)

        toolbar.add_top_bar(header)
        self._nav_view.set_child(toolbar)

    def _create_sidebar_page(self):
        """Create the sidebar navigation page."""
        page = Adw.NavigationPage.new(self._content_stack, "Sidebar")
        page.set_title("Tadpole")

        # Sidebar list
        self._sidebar_list = Gtk.ListBox()
        self._sidebar_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._sidebar_list.connect("row-activated", self._on_sidebar_row_activated)

        # Add sidebar items
        self._add_sidebar_items()

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self._sidebar_list)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_width(200)

        page.set_child(scrolled)
        return page

    def _add_sidebar_items(self):
        """Add items to sidebar list."""
        # Device selector
        self._device_row = Adw.ActionRow(title="Device")
        self._device_row.add_prefix(Gtk.Image.new_from_icon_name("phone-symbolic"))

        self._device_combo = Adw.ComboRow(title="Device")
        self._device_combo.set_model(Gtk.StringList.new(["No devices"]))
        self._device_combo.set_selected(0)
        self._device_combo.connect("notify::selected", self._on_device_combo_changed)
        self._device_row.add_suffix(self._device_combo)
        self._sidebar_list.append(self._device_row)

        # Refresh button
        refresh_row = Adw.ActionRow(title="Refresh Devices")
        refresh_row.add_prefix(Gtk.Image.new_from_icon_name("view-refresh-symbolic"))
        refresh_row.set_activatable(True)
        refresh_row.connect("activated", lambda r: self._app._refresh_devices())
        self._sidebar_list.append(refresh_row)

        # Separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self._sidebar_list.append(separator)

        # Navigation items (will change based on mode)
        self._nav_items = []
        self._update_nav_items()

    def _update_nav_items(self):
        """Update navigation items based on current mode."""
        # Clear existing nav items (keep first 3 rows: device, refresh, separator)
        children = []
        child = self._sidebar_list.get_first_child()
        while child:
            children.append(child)
            child = child.get_next_sibling()

        # Remove items after separator (index 2)
        for i, child in enumerate(children):
            if i > 2:
                self._sidebar_list.remove(child)

        # Add mode-specific items
        if self._app._mode == "adb":
            items = [
                ("Overview", "applications-system-symbolic", "overview"),
                ("Apps", "package-x-generic-symbolic", "apps"),
                ("Files", "folder-symbolic", "files"),
                ("Shell", "utilities-terminal-symbolic", "shell"),
                ("Logcat", "text-x-log-symbolic", "logcat"),
                ("Screen", "video-display-symbolic", "screen"),
            ]
        else:
            items = [
                ("Device", "drive-harddisk-symbolic", "fb_device"),
                ("Flash", "media-flash-symbolic", "fb_flash"),
                ("Partitions", "drive-removable-media-symbolic", "fb_partitions"),
                ("Bootloader", "system-lock-screen-symbolic", "fb_bootloader"),
                ("Reboot", "system-reboot-symbolic", "fb_reboot"),
            ]

        for title, icon, tag in items:
            row = Adw.ActionRow(title=title)
            row.add_prefix(Gtk.Image.new_from_icon_name(icon))
            row.set_activatable(True)
            row.set_tag(tag)
            row.connect("activated", self._on_nav_row_activated, tag)
            self._sidebar_list.append(row)
            self._nav_items.append((row, tag))

    def _on_header_mode_changed(self, combo, param):
        """Handle mode change from header bar."""
        mode = "adb" if combo.get_selected() == 0 else "fastboot"
        if mode != self._app._mode:
            action = self._app.lookup_action(f"mode-{mode}")
            if action:
                action.change_state(GLib.Variant.new_string(mode))

    def _on_device_combo_changed(self, combo, param):
        """Handle device combo change."""
        selected = combo.get_selected()
        if selected > 0 and selected < len(self._app._devices):
            device = self._app._devices[selected - 1]
            self._app.current_serial = device.serial

    def _on_sidebar_row_activated(self, listbox, row):
        """Handle sidebar row activation."""
        if hasattr(row, 'get_tag'):
            tag = row.get_tag()
            if tag:
                self._switch_content(tag)

    def _on_nav_row_activated(self, row, tag):
        """Handle navigation row activation."""
        self._switch_content(tag)

    def _switch_content(self, tag):
        """Switch content view based on tag."""
        # Map tag to view
        views = {
            "overview": self._create_overview_view,
            "apps": self._create_apps_view,
            "files": self._create_files_view,
            "shell": self._create_shell_view,
            "logcat": self._create_logcat_view,
            "screen": self._create_screen_view,
            "fb_device": self._create_fb_device_view,
            "fb_flash": self._create_fb_flash_view,
            "fb_partitions": self._create_fb_partitions_view,
            "fb_bootloader": self._create_fb_bootloader_view,
            "fb_reboot": self._create_fb_reboot_view,
        }

        if tag in views:
            view = views[tag]()
            self._content_stack.add_named(view, tag)
            self._content_stack.set_visible_child_name(tag)

    def _show_placeholder(self):
        """Show placeholder content."""
        placeholder = Adw.StatusPage()
        placeholder.set_title("Select a device")
        placeholder.set_description("Connect an Android device via USB or WiFi to get started.")
        placeholder.set_icon_name("phone-symbolic")
        self._content_stack.add_named(placeholder, "placeholder")
        self._content_stack.set_visible_child_name("placeholder")

    def _create_overview_view(self):
        """Create device overview view."""
        page = Adw.PreferencesPage()
        page.set_title("Device Overview")

        # Device info group
        group = Adw.PreferencesGroup()
        group.set_title("Device Information")

        self._overview_name = Adw.ActionRow(title="Model")
        self._overview_name.add_suffix(Gtk.Label(label="Select a device"))
        group.add(self._overview_name)

        self._overview_brand = Adw.ActionRow(title="Brand")
        group.add(self._overview_brand)

        self._overview_android = Adw.ActionRow(title="Android Version")
        group.add(self._overview_android)

        self._overview_sdk = Adw.ActionRow(title="SDK")
        group.add(self._overview_sdk)

        self._overview_abi = Adw.ActionRow(title="ABI")
        group.add(self._overview_abi)

        self._overview_battery = Adw.ActionRow(title="Battery")
        group.add(self._overview_battery)

        self._overview_screen = Adw.ActionRow(title="Screen")
        group.add(self._overview_screen)

        page.add(group)

        # Actions group
        actions_group = Adw.PreferencesGroup()
        actions_group.set_title("Actions")

        for title, action_name in [
            ("Reboot to Bootloader", "reboot-bootloader"),
            ("Reboot to Recovery", "reboot-recovery"),
            ("Reboot to Fastbootd", "reboot-fastbootd"),
            ("Reboot System", "reboot-system"),
            ("ADB Root", "adb-root"),
            ("Sideload ZIP…", "sideload"),
        ]:
            row = Adw.ActionRow(title=title)
            row.set_activatable(True)
            row.connect("activated", lambda r, a=action_name: self._on_action(a))
            actions_group.add(row)

        page.add(actions_group)

        return page

    def _create_apps_view(self):
        """Create apps management view."""
        page = Adw.PreferencesPage()
        page.set_title("Apps")

        # Toolbar
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.Label(label="Apps"))

        install_btn = Gtk.Button(label="Install APK…")
        install_btn.add_css_class("suggested-action")
        install_btn.connect("clicked", lambda b: self._on_action("install-apk"))
        header.pack_end(install_btn)

        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.connect("clicked", lambda b: self._refresh_apps())
        header.pack_start(refresh_btn)

        toolbar.add_top_bar(header)

        # Apps list
        self._apps_list = Gtk.ListBox()
        self._apps_list.set_selection_mode(Gtk.SelectionMode.SINGLE)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self._apps_list)
        scrolled.set_vexpand(True)

        # Combine toolbar and list
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(toolbar)
        box.append(scrolled)

        page.add(box)
        return box

    def _create_files_view(self):
        """Create file browser view."""
        page = Adw.PreferencesPage()
        page.set_title("Files")

        # Path bar
        path_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        path_box.set_margin_top(6)
        path_box.set_margin_bottom(6)
        path_box.set_margin_start(12)
        path_box.set_margin_end(12)

        up_btn = Gtk.Button(label="Up")
        up_btn.connect("clicked", lambda b: self._navigate_up())
        path_box.append(up_btn)

        self._path_entry = Gtk.Entry()
        self._path_entry.set_text("/sdcard")
        self._path_entry.set_hexpand(True)
        self._path_entry.connect("activate", lambda e: self._refresh_files())
        path_box.append(self._path_entry)

        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.connect("clicked", lambda b: self._refresh_files())
        path_box.append(refresh_btn)

        # Files list
        self._files_list = Gtk.ListBox()
        self._files_list.set_selection_mode(Gtk.SelectionMode.SINGLE)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self._files_list)
        scrolled.set_vexpand(True)

        # Action buttons
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        action_box.set_margin_top(6)
        action_box.set_margin_bottom(6)
        action_box.set_margin_start(12)
        action_box.set_margin_end(12)

        pull_btn = Gtk.Button(label="Pull…")
        pull_btn.connect("clicked", lambda b: self._on_action("pull-file"))
        action_box.append(pull_btn)

        push_btn = Gtk.Button(label="Push…")
        push_btn.add_css_class("suggested-action")
        push_btn.connect("clicked", lambda b: self._on_action("push-file"))
        action_box.append(push_btn)

        delete_btn = Gtk.Button(label="Delete")
        delete_btn.add_css_class("destructive-action")
        delete_btn.connect("clicked", lambda b: self._on_action("delete-file"))
        action_box.append(delete_btn)

        # Combine
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(path_box)
        box.append(scrolled)
        box.append(action_box)

        page.add(box)
        return box

    def _create_shell_view(self):
        """Create shell terminal view."""
        page = Adw.PreferencesPage()
        page.set_title("Shell")

        # Output
        self._shell_output = Gtk.TextView()
        self._shell_output.set_editable(False)
        self._shell_output.set_monospace(True)
        self._shell_output.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self._shell_output)
        scrolled.set_vexpand(True)

        # Input
        self._shell_input = Gtk.Entry()
        self._shell_input.set_placeholder_text("Enter shell command...")
        self._shell_input.connect("activate", self._on_shell_command)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.append(scrolled)
        box.append(self._shell_input)

        page.add(box)
        return box

    def _create_logcat_view(self):
        """Create logcat view."""
        page = Adw.PreferencesPage()
        page.set_title("Logcat")

        # Controls
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        controls.set_margin_top(6)
        controls.set_margin_bottom(6)
        controls.set_margin_start(12)
        controls.set_margin_end(12)

        controls.append(Gtk.Label(label="Level:"))
        self._logcat_level = Adw.ComboRow()
        self._logcat_level.set_model(Gtk.StringList.new(["Verbose", "Debug", "Info", "Warning", "Error", "Fatal"]))
        self._logcat_level.set_selected(2)
        controls.append(self._logcat_level)

        controls.append(Gtk.Label(label="Filter:"))
        self._logcat_filter = Gtk.Entry()
        self._logcat_filter.set_placeholder_text("e.g. ActivityManager:I *:S")
        self._logcat_filter.set_hexpand(True)
        controls.append(self._logcat_filter)

        start_btn = Gtk.Button(label="Start")
        start_btn.add_css_class("suggested-action")
        start_btn.connect("clicked", lambda b: self._on_action("logcat-start"))
        controls.append(start_btn)

        stop_btn = Gtk.Button(label="Stop")
        stop_btn.connect("clicked", lambda b: self._on_action("logcat-stop"))
        controls.append(stop_btn)

        clear_btn = Gtk.Button(label="Clear")
        clear_btn.connect("clicked", lambda b: self._on_action("logcat-clear"))
        controls.append(clear_btn)

        save_btn = Gtk.Button(label="Save…")
        save_btn.connect("clicked", lambda b: self._on_action("logcat-save"))
        controls.append(save_btn)

        # Output
        self._logcat_output = Gtk.TextView()
        self._logcat_output.set_editable(False)
        self._logcat_output.set_monospace(True)
        self._logcat_output.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self._logcat_output)
        scrolled.set_vexpand(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(controls)
        box.append(scrolled)

        page.add(box)
        return box

    def _create_screen_view(self):
        """Create screen view."""
        page = Adw.PreferencesPage()
        page.set_title("Screen")

        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_top(6)
        toolbar.set_margin_bottom(6)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)

        capture_btn = Gtk.Button(label="Capture")
        capture_btn.add_css_class("suggested-action")
        capture_btn.connect("clicked", lambda b: self._on_action("screen-capture"))
        toolbar.append(capture_btn)

        self._live_check = Gtk.CheckButton(label="Live (1.5s)")
        toolbar.append(self._live_check)

        save_btn = Gtk.Button(label="Save PNG…")
        save_btn.connect("clicked", lambda b: self._on_action("screen-save"))
        toolbar.append(save_btn)

        toolbar.append(Gtk.Label(label="Click screenshot to tap"))

        # Screen display
        self._screen_image = Gtk.Picture()
        self._screen_image.set_content_fit(Gtk.ContentFit.CONTAIN)
        self._screen_image.set_vexpand(True)
        self._screen_image.set_hexpand(True)

        # Navigation keys
        keys_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        keys_box.set_margin_top(6)
        keys_box.set_margin_bottom(6)
        keys_box.set_margin_start(12)
        keys_box.set_margin_end(12)
        keys_box.set_halign(Gtk.Align.CENTER)

        for label, keycode in [
            ("Back", 4), ("Home", 3), ("Recents", 187),
            ("Power", 26), ("Vol +", 24), ("Vol -", 25),
        ]:
            btn = Gtk.Button(label=label)
            btn.connect("clicked", lambda b, k=keycode: self._send_keyevent(k))
            keys_box.append(btn)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(toolbar)
        box.append(self._screen_image)
        box.append(keys_box)

        page.add(box)
        return box

    # Fastboot views (placeholders)
    def _create_fb_device_view(self):
        page = Adw.PreferencesPage()
        page.set_title("Fastboot Device")
        page.add(Adw.PreferencesGroup(title="Fastboot Variables"))
        return page

    def _create_fb_flash_view(self):
        page = Adw.PreferencesPage()
        page.set_title("Flash")
        page.add(Adw.PreferencesGroup(title="Flash Options"))
        return page

    def _create_fb_partitions_view(self):
        page = Adw.PreferencesPage()
        page.set_title("Partitions")
        page.add(Adw.PreferencesGroup(title="Partitions"))
        return page

    def _create_fb_bootloader_view(self):
        page = Adw.PreferencesPage()
        page.set_title("Bootloader")
        page.add(Adw.PreferencesGroup(title="Bootloader Actions"))
        return page

    def _create_fb_reboot_view(self):
        page = Adw.PreferencesPage()
        page.set_title("Reboot")
        page.add(Adw.PreferencesGroup(title="Reboot Options"))
        return page

    # Event handlers
    def on_mode_changed(self, mode):
        """Called when mode changes."""
        self._update_nav_items()
        self._header_mode.set_selected(0 if mode == "adb" else 1)
        self._show_placeholder()

    def on_device_changed(self, serial):
        """Called when selected device changes."""
        self._update_device_info(serial)

    def update_device_list(self, devices):
        """Update device list in UI."""
        model = Gtk.StringList.new(["No devices"])
        for d in devices:
            if d.is_ready:
                model.append(d.display_name)

        self._device_combo.set_model(model)

        # Restore selection if possible
        if self._app._current_serial:
            for i, d in enumerate(devices):
                if d.serial == self._app._current_serial:
                    self._device_combo.set_selected(i + 1)
                    break

    def _update_device_info(self, serial):
        """Update device info in overview."""
        if not serial or not self._app._adb_service:
            return

        def task_func(task, source_object, cancellable):
            try:
                info = self._app._adb_service.get_device_info(serial)
                battery = self._app._adb_service.get_battery(serial)
                screen = self._app._adb_service.get_screen_size(serial)
                task.return_value((info, battery, screen))
            except Exception as e:
                task.return_error(e)

        def task_done(source_object, result):
            try:
                info, battery, screen = result.propagate_value()
                if hasattr(self, '_overview_name'):
                    self._overview_name.set_subtitle(info.display_name or serial)
                    self._overview_brand.set_subtitle(info.brand or "-")
                    self._overview_android.set_subtitle(info.android or "-")
                    self._overview_sdk.set_subtitle(info.sdk or "-")
                    self._overview_abi.set_subtitle(info.abi or "-")
                    bat_text = f"{battery.level} {battery.status} {battery.temperature}".strip()
                    self._overview_battery.set_subtitle(bat_text or "-")
                    self._overview_screen.set_subtitle(screen or "-")
            except Exception as e:
                print(f"Error updating device info: {e}")

        task = Gio.Task.new(self, None, task_done)
        task.run_in_thread(task_func)

    def _on_action(self, action_name):
        """Handle generic actions."""
        # TODO: Implement actions
        print(f"Action: {action_name}")

    def _refresh_apps(self):
        """Refresh apps list."""
        if not self._app._current_serial or not self._app._adb_service:
            return

        def task_func(task, source_object, cancellable):
            try:
                apps = self._app._adb_service.list_packages(self._app._current_serial)
                task.return_value(apps)
            except Exception as e:
                task.return_error(e)

        def task_done(source_object, result):
            try:
                apps = result.propagate_value()
                self._apps_list.remove_all()
                for app in apps:
                    row = Adw.ActionRow(title=app.package)
                    row.set_subtitle(app.version or "Unknown")
                    self._apps_list.append(row)
            except Exception as e:
                print(f"Error refreshing apps: {e}")

        task = Gio.Task.new(self, None, task_done)
        task.run_in_thread(task_func)

    def _refresh_files(self):
        """Refresh files list."""
        if not self._app._current_serial or not self._app._adb_service:
            return

        path = self._path_entry.get_text()

        def task_func(task, source_object, cancellable):
            try:
                files = self._app._adb_service.list_files(self._app._current_serial, path)
                task.return_value(files)
            except Exception as e:
                task.return_error(e)

        def task_done(source_object, result):
            try:
                files = result.propagate_value()
                self._files_list.remove_all()
                for f in files:
                    row = Adw.ActionRow(title=f.name)
                    row.set_subtitle(f"{f.type.value} • {f.size} bytes")
                    self._files_list.append(row)
            except Exception as e:
                print(f"Error refreshing files: {e}")

        task = Gio.Task.new(self, None, task_done)
        task.run_in_thread(task_func)

    def _navigate_up(self):
        """Navigate up one directory."""
        path = self._path_entry.get_text()
        if path != "/":
            import re
            parent = re.sub(r"/[^/]+/?$", "", path) or "/"
            self._path_entry.set_text(parent)
            self._refresh_files()

    def _on_shell_command(self, entry):
        """Handle shell command entry."""
        if not self._app._current_serial or not self._app._adb_service:
            return

        cmd = entry.get_text().strip()
        if not cmd:
            return

        entry.set_text("")

        def task_func(task, source_object, cancellable):
            try:
                result = self._app._adb_service.shell(self._app._current_serial, cmd)
                task.return_value((cmd, result))
            except Exception as e:
                task.return_error(e)

        def task_done(source_object, result):
            try:
                cmd, output = result.propagate_value()
                buffer = self._shell_output.get_buffer()
                end = buffer.get_end_iter()
                buffer.insert(end, f"$ {cmd}\n{output}\n")
                self._shell_output.scroll_to_iter(buffer.get_end_iter(), 0, False, 0, 0)
            except Exception as e:
                buffer = self._shell_output.get_buffer()
                end = buffer.get_end_iter()
                buffer.insert(end, f"Error: {e}\n")

        task = Gio.Task.new(self, None, task_done)
        task.run_in_thread(task_func)

    def _send_keyevent(self, keycode):
        """Send keyevent to device."""
        if not self._app._current_serial or not self._app._adb_service:
            return

        def task_func(task, source_object, cancellable):
            try:
                result = self._app._adb_service.input_keyevent(self._app._current_serial, keycode)
                task.return_value(result)
            except Exception as e:
                task.return_error(e)

        task = Gio.Task.new(self, None, lambda s, r: None)
        task.run_in_thread(task_func)


def main():
    """Main entry point."""
    app = TadpoleApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
