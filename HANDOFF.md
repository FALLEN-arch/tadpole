# Tadpole: handoff notes

Tadpole is a Linux-only Tkinter GUI for adb and fastboot (repo: FALLEN-arch/tadpole). This file is for whoever picks the project up next. Read it top to bottom before changing anything.

## State at handoff

Done in the last session:

1. **Icon integrated.** `icon.png` (1254 px, 1.2 MB, kept in the repo root as source art) was resized to `src/tadpole/assets/tadpole-256.png` and `tadpole-64.png`. `App.set_icon()` loads both with `iconphoto`. The window class is set to `tadpole` (Tk capitalises it to `Tadpole`), which matches `StartupWMClass=Tadpole` in the generated `.desktop` file so GNOME/KDE group the window under the launcher.
2. **Duplicates merged.** The repo root used to hold stray `gui.py`, `fastboot.py` and `run.sh`. The root files were *newer* than their `src/` and `scripts/` counterparts, so their changes were carried over before deleting them:
   - terminal `-s SERIAL` handling and `adb`/`fastboot` prefix override (now `util.parse_terminal`),
   - `fastboot.version()` tolerating empty output,
   - the venv-based launcher, now at `scripts/run.sh` (it errors with "run install.sh" if `.venv` is missing; that is intentional).
3. **`gui.py` split** (it was ~1,100 lines). See "Layout" below.
4. **Tests** (60, all passing, no display or phone needed).
5. **Packaging**: new `install.sh` flags, `--install-desktop` / `--uninstall-desktop` CLI, udev notes.
6. **Startup checks**: friendly error if Tk or tkinterdnd2 is missing, in-app warning if adb/fastboot is not on `PATH`, `tadpole --check`.

## Verification gaps (important)

The previous session's sandbox had **no tkinter, no adb, no fastboot, no network and no display**. So:

- **The GUI has never been run for real after the split.** It was checked by (a) a stdlib static scan for undefined names and unused imports, (b) the fake-Tk smoke test in `tests/test_gui_smoke.py`, which builds every tab and exercises theme switching and `run_cmd`. That catches wiring mistakes, not layout, colours or event behaviour.
- `install.sh` was only tested for `--help`, bad options and `--uninstall`. The pip install step and the full install were **not** run.
- Nothing was tested against a real device.

First thing to do on a real Linux machine: run the manual checklist below.

## Manual checklist (needs a real desktop, ideally a phone)

- [ ] `./install.sh`, then launch from the application menu: icon shows in the menu, title bar and taskbar/dock (check on X11 *and* Wayland if possible; Wayland needs the `.desktop` match).
- [ ] `./scripts/run.sh --check` and `tadpole --version`.
- [ ] Temporarily hide `adb` from `PATH`: a "Missing tools" dialog appears once, ~300 ms after start.
- [ ] Uninstall python3-tk (or use a venv without it): `tadpole` prints "Tadpole cannot start" instead of a traceback.
- [ ] Toggle the theme; restart; theme persists. Check the terminal, logcat and shell text boxes recolour.
- [ ] Terminal dock: `devices`, `adb -s <serial> shell id`, `fastboot getvar all` while in ADB mode, `adb -s` (should show an error).
- [ ] Every ADB tab: Overview, Apps (incl. drop an `.apk`), Files, Shell, Logcat start/stop/filter/save, Screen capture + tap.
- [ ] Every Fastboot tab incl. drop an `.img` onto the window, flash progress bar, typed confirmations.
- [ ] `./install.sh --uninstall` removes the menu entry, icon and `.venv`.

## Layout

```
install.sh              install / --no-system / --uninstall
scripts/run.sh          launcher using .venv (restored from the old root run.sh)
src/tadpole/
  gui.py                CLI entry point (`tadpole`): argparse flags; imports NO Tk
  app.py                App(BaseTk, AdbTabs, FastbootTabs): top bar, terminal dock, polling, theme, DnD
  tabs/adb_tabs.py      AdbTabs mixin: b_overview, b_apps, b_files, b_shell, b_logcat, b_screen, stop_log
  tabs/fastboot_tabs.py FastbootTabs mixin: load_vars, b_fbdevice, b_flash, b_parts, b_boot, b_reboot
  widgets.py            make_text, make_tree, SideNav, TEXTS (all themed Text widgets)
  theme.py              PALETTES, set_palette, tag_colors, MONO
  config.py             CONF (~/.tadpole), load_json, save_json
  util.py               flash_pct, human, NAME_RE, parse_terminal  (pure, unit tested)
  deps.py               missing_tools, python_problems, install_hint, tools_message (pure)
  desktop.py            install()/uninstall() of the .desktop entry + icon
  adb.py, fastboot.py   subprocess wrappers (argv lists, never a shell)
tests/                  unittest-style (also run by pytest); tk_stub.py fakes tkinter
```

## Rules and gotchas

- **Read colours as `theme.BG`, never `from .theme import BG`.** `set_palette()` rewrites the module's globals on a theme switch; a `from` import would freeze the old colour. `theme.tag_colors` relies on those same globals (hence the `noqa: F821`).
- Tabs are mixins. They rely on `App` providing `self.adb()`, `self.fbr()`, `self.bg()`, `self.log()`, `self.need()`, `self.typed()`, `self.ser`, `self.q`, `self.nb`, `self.preset`, `self.flashpath`, `self.fbvars`, `self.logproc`, `self.logbuf`, `self.shot`, `self.presets`. A tab method returns its refresh callback (or `None`); `App.build` stores it as `frame.on_show`.
- `gui.py` must stay importable without Tk: `deps.python_problems()` runs *before* `from .app import main`. Do not add Tk imports to `gui.py`, `deps.py`, `util.py`, `config.py`, `theme.py` or `desktop.py`.
- tkinterdnd2 remains a **hard requirement** (drag and drop is a core feature); it is only checked early so the error is friendly.
- Config path logic in `config.py` falls back to the old `~/.adb-studio` folder if `~/.tadpole` does not exist. Tests patch `tadpole.config.CONF`.
- `tests/tk_stub.py` makes every widget accept any call. If you add a widget class or a `tk.` function the fake lacks, extend the stub rather than loosening a test.
- `run_cmd` behaviour change: when the terminal line is invalid (bad quoting or `-s` with no serial) the typed text is now left in the entry so it can be corrected. Previously the `-s` error cleared it.
- Destructive fastboot actions require typed confirmations (`FLASH`, `ERASE`, `UNLOCK`, `LOCK`, `WIPE`). Keep that.
- `desktop.launch_command()` uses the `tadpole` script next to the running Python (so it points into `.venv`), else `python -m tadpole`.

## Running things

```bash
python3 -m unittest discover -s tests -t .      # no extra packages needed
.venv/bin/python -m pytest                      # after: pip install -e '.[dev]'
./scripts/run.sh --check                        # dependency report
```

## Not done / next steps

From the earlier improvement list (items 1 to 5 are done):

6. Settings and UX: remember window size and last tab; keyboard shortcuts (Ctrl+R refresh, Ctrl+L clear terminal); "Copy" button for terminal output; progress bars for APK install and push/pull (only flashing has one now).
7. Safety: check a selected `.img` matches the chosen partition name; log destructive actions to a file.
8. Housekeeping: CHANGELOG, GitHub Actions running the tests and a linter (ruff), screenshots in the README.

Packaging ideas not attempted (could not be built or tested in the sandbox): AppImage, Flatpak. A Flatpak needs USB device permissions and `adb`/`fastboot` bundled, so it is not trivial.

Smaller loose ends:

- The `Screen` tab's `tick()` loop and the logcat `flush()` loop reschedule forever; fine for now, but worth checking CPU use when idle.
- `adb.stream()` is currently unused by the GUI.
- `icon.png` (1.2 MB) in the root is source art only; the app uses the resized copies in `assets/`. Move it to a `docs/` or `artwork/` folder if the root should be tidier.
- No linter config yet; the stdlib scan used last session lives only in that session. Adding ruff (`ruff check`) would replace it.
