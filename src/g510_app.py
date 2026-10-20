#!/usr/bin/env python3
"""
G510 LCD Control App.

Architecture: sidebar navigation with one stacked page per feature.
Existing feature widgets retain their independent controls and lifecycle.

Phase 1: Backlight tab (color/brightness + service control).
         G-Keys tab (record/assign macros to G1-G18 per M1/M2/M3 profile).
Phase 2: Custom Screens tab (AIDA64-style sensor dashboard builder for
         LCD screens, with a live preview of the real LCD output).
"""
import sys
import json
import shutil
import subprocess
import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QComboBox, QPushButton, QLabel,
    QMessageBox, QDialog, QLineEdit, QSpinBox, QFrame, QScrollArea,
    QFileDialog, QInputDialog, QStatusBar, QListWidget, QListWidgetItem,
    QCheckBox, QSizePolicy, QShortcut, QMenu, QColorDialog,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QProcess
from PyQt5.QtGui import QIcon, QImage, QPixmap, QColor, QFontMetrics, QKeySequence
import evdev
from evdev import ecodes

import g510_canvas
from g510_theme import STYLESHEET
from g510_layouts import (
    LCD_WIDTH,
    LCD_HEIGHT,
    DEFAULT_SCREEN_PRESETS,
    SCREEN_NAMES,
    PRESET_NAMES,
    CPU_CORE_SENSOR_COUNT,
    MAX_SENSOR_ELEMENTS,
    GAME_BOUNDS_BASE,
    build_layout_preset,
    SENSOR_CHOICES,
    SENSOR_LABELS,
    DEFAULT_SENSOR_DISPLAY_LABELS,
    DATETIME_FORMAT_CHOICES,
    DATETIME_FORMAT_DEFAULTS,
    SENSOR_DESCRIPTIONS,
    BAR_CAPABLE_SENSORS,
    LEGACY_SENSOR_ALIASES,
    CUSTOM_SCREEN_KEYS,
    MAX_IMAGES_PER_SCREEN,
    MAX_TEXTS_PER_SCREEN,
    MAX_VISUALIZERS_PER_SCREEN,
    DEFAULT_VISUALIZER_WIDTH,
    DEFAULT_VISUALIZER_HEIGHT,
    TEXT_CHAR_PX,
    FONT_SIZE_CHOICES,
    MAX_BAR_FONT_SIZE,
    FONT_SIZE_SCALE,
)
from g510_screen_canvas import (
    ScreenPreviewCanvas, PREVIEW_SCALE, ELEMENT_HIT_W, ELEMENT_HIT_H,
    RESIZE_HANDLE_PX, MIN_BAR_WIDTH, MAX_BAR_WIDTH,
    MIN_BAR_HEIGHT, MAX_BAR_HEIGHT, MIN_IMAGE_SIZE,
)
import g510_layout_store as layout_store
from g510_layout_store import GAME_DASHBOARD_COMPONENTS
import g510_preview as preview_renderer
import g510_game_colors as game_colors
from g510_screen_keys import (
    action_labels, load_bindings, save_bindings, CLOCK_ACTIONS,
    next_screen, show_screen, read_screen, perform_action,
    load_screens, load_screen_catalog, save_screen_catalog,
    CLOCK_LAYOUTS, load_clock_layout, save_clock_layout,
    DESIGN_ACTIONS, SCREEN_DESIGNS, load_screen_design, save_screen_design,
)

PROJECT_DIR = Path(__file__).resolve().parent.parent  # repo root (this file lives in src/)
LED_DIR = Path("/sys/class/leds/g15::kbd_backlight")
DEFAULTS_SCRIPT = PROJECT_DIR / "scripts" / "set-backlight-color.sh"
# The udev rule (99-g510-lcd.rules) has this exact path baked in at
# install time (see install.sh), so this location can't just move --
# doing that alone, without also re-running install.sh's sudo udev
# step, would leave the live udev rule pointing at a script that stops
# getting updated (replugging the keyboard would silently restore a
# stale color). Also writing the same content to DATA_DIR so a future
# packaged install (whose /usr/lib/g510-lcd is root-owned -- this
# PROJECT_DIR-relative write would fail there) has a real, current
# copy ready once its own udev rule points at the right place -- a
# deliberately deferred gap, documented in packaging/g510-lcd/README.md.
# (DEFAULTS_SCRIPT_DATA_DIR is set further down, once DATA_DIR exists.)
MAIN_KEYBOARD_DEVICE = "/dev/input/by-id/usb-Logitech_G510s_Gaming_Keyboard-event-kbd"
STATS_BINARY = PROJECT_DIR / "src" / "g510_lcd_stats"

# Your own macros/custom-screens config and imported images live under
# ~/.local/share/g510-lcd, independent of where the program itself is
# installed from (a dev checkout via install.sh, or a real package
# under a fixed /usr/lib/g510-lcd) -- so a package upgrade never
# touches what you've actually configured. Mirrors the identical
# data_dir()/migrate_*_if_needed() logic in g510_lcd_stats.c -- both
# sides need to agree on this path independently since the C binary
# and this GUI both read/write the same files without talking to each
# other directly.
DATA_DIR = Path.home() / ".local" / "share" / "g510-lcd"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _migrate_file_if_needed(old_path: Path, new_path: Path):
    if new_path.exists() or not old_path.exists():
        return
    new_path.write_bytes(old_path.read_bytes())


def _migrate_dir_if_needed(old_dir: Path, new_dir: Path):
    if not old_dir.is_dir():
        return
    new_dir.mkdir(parents=True, exist_ok=True)
    for f in old_dir.iterdir():
        if f.is_file():
            _migrate_file_if_needed(f, new_dir / f.name)


_migrate_file_if_needed(PROJECT_DIR / "custom_screens.txt", DATA_DIR / "custom_screens.txt")
_migrate_file_if_needed(PROJECT_DIR / "macros.json", DATA_DIR / "macros.json")
_migrate_dir_if_needed(PROJECT_DIR / "custom_screen_images", DATA_DIR / "custom_screen_images")

MACROS_FILE = DATA_DIR / "macros.json"
CUSTOM_SCREENS_FILE = DATA_DIR / "custom_screens.txt"
DEFAULTS_SCRIPT_DATA_DIR = DATA_DIR / "set-backlight-color.sh"

def active_profile_file():
    import os
    runtime = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    return Path(runtime, "g510_macro_profile")


def read_active_screen_num():
    """Mirrors g510_lcd_buttons.c's screen_state_path()/read_screen() --
    the same runtime state file g510_lcd_buttons.c writes and
    g510_lcd_stats.c itself reads to decide what to actually draw, so
    this reflects reality rather than a guess.

    Corrected after a real report ("the hardcoded L1 screen, not the
    clock, the stats, are not visible") -- 0 and 1 are NOT both "the
    clock". Reading g510_lcd_stats.c's own screen-select logic
    directly: `screen == 1` draws the clock, `screen >= 2` draws
    a custom screen, and everything else -- which in practice
    means 0, the state before any L-button has ever been pressed --
    draws the CPU/RAM/VRAM/TEMP stats screen. An earlier version of
    this function collapsed 0 into 1, so the mirror silently showed
    the clock instead of stats whenever the real hardware was on 0.
    render_preview()/--preview accept screen IDs directly (same atoi(argv[2])
    the live daemon's read_screen() feeds into), so no translation is
    needed here beyond passing the real value through unchanged.

    Falls back to 0 (stats -- the real default) for anything
    unreadable: state file missing (service not running yet),
    malformed, or a stray value outside the real 0-5 range."""
    import os
    runtime = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    try:
        s = int(Path(runtime, "g510lcd_screen").read_text().strip())
    except Exception:
        return 0
    return s if s >= 0 else 0

COLOR_RGB = {
    "Blauviolett": (110, 0, 255),
    "Rot": (255, 0, 0),
    "Grün": (0, 255, 0),
    "Blau": (0, 0, 255),
    "Lila": (128, 0, 128),
    "Cyan": (0, 255, 255),
    "Orange": (255, 100, 0),
    "Pink": (255, 0, 150),
    "Weiß": (255, 255, 255),
}

# Profile: LED-Farbe + anzuzeigender LCD-Bildschirm (0 = Statistik, 2-5 = L2-L5)
PROFILES = {
    "Spiel": {"rgb": (255, 0, 0), "screen": 2},
    "Arbeit": {"rgb": (0, 120, 255), "screen": 4},
    "Nacht": {"rgb": (60, 0, 0), "screen": 1},
}


def read_current_rgb():
    try:
        r, g, b = (int(x) for x in (LED_DIR / "multi_intensity").read_text().split())
        return (r, g, b)
    except Exception:
        return None


def write_defaults_script(rgb, brightness_val):
    script = f"""#!/bin/bash
# Applies the chosen keyboard backlight color. Run automatically by
# 99-g510-lcd.rules whenever the LED device appears (boot or replug).
# Auto-updated by g510_app.py every time you click Apply or Set as Default.
echo {brightness_val} > /sys/class/leds/g15::kbd_backlight/brightness
echo "{rgb[0]} {rgb[1]} {rgb[2]}" > /sys/class/leds/g15::kbd_backlight/multi_intensity
"""
    # The currently-installed udev rule has DEFAULTS_SCRIPT's path baked
    # in, so it has to keep being written for replug-restore to keep
    # working -- but this fails with PermissionError in a packaged
    # install (/usr/lib/g510-lcd is root-owned), which is expected
    # there, not a real error to surface.
    try:
        DEFAULTS_SCRIPT.write_text(script)
        DEFAULTS_SCRIPT.chmod(0o755)
    except PermissionError:
        pass
    DEFAULTS_SCRIPT_DATA_DIR.write_text(script)
    DEFAULTS_SCRIPT_DATA_DIR.chmod(0o755)


# Brightness used to be user-adjustable here, but real testing (writing
# 50/128/200/100 to the sysfs brightness file and reading each back
# immediately) confirmed it's pinned at max_brightness (255) regardless
# of what's written -- a real kernel/driver-level limitation on this
# hardware, not a display bug. Removed rather than kept as dead,
# misleading UI; MAX_BRIGHTNESS documents why 255 is hardcoded below,
# not guessed.
MAX_BRIGHTNESS = 255


def apply_backlight(rgb):
    """Writes the LED sysfs files AND rewrites set-backlight-color.sh so
    this becomes the new permanent boot default (matches the behavior
    already established by g510-backlight-apply.sh -- same contract).
    Takes a real (r, g, b) tuple directly rather than a preset name --
    the picker UI now also accepts an arbitrary hex color, not just
    the fixed COLOR_RGB presets, so a name-keyed lookup here would
    reject anything typed by hand."""
    try:
        (LED_DIR / "multi_intensity").write_text(f"{rgb[0]} {rgb[1]} {rgb[2]}")
        (LED_DIR / "brightness").write_text(str(MAX_BRIGHTNESS))
    except PermissionError as e:
        return False, f"Zugriff verweigert beim Schreiben nach {LED_DIR} – prüfe, ob die udev-Regel (99-g510-lcd.rules) installiert ist: {e}"

    write_defaults_script(rgb, MAX_BRIGHTNESS)
    return True, None


def set_as_default(rgb):
    """Persist-only: updates set-backlight-color.sh (the boot default)
    WITHOUT touching the live backlight right now -- distinct from
    Apply, which does both. Lets you keep previewing other colors live
    without losing a default you've already decided on. Same (r, g, b)
    tuple convention as apply_backlight()."""
    write_defaults_script(rgb, MAX_BRIGHTNESS)
    return True, None


ALL_SERVICES = [
    "g510-game-colors.service",
    "g510-backlight.service",
    "g510-lcd-stats.service",
    "g510-lcd-buttons.service",
    "g510-macro-daemon.service",
]


def run_systemctl(action):
    try:
        subprocess.run(
            ["systemctl", "--user", action] + ALL_SERVICES,
            check=True, capture_output=True, text=True,
        )
        return True, None
    except subprocess.CalledProcessError as e:
        return False, e.stderr or str(e)


MACRO_RECORD_LED = Path("/sys/class/leds/g15::macro_record/brightness")


def read_macro_record_led():
    try:
        return int(MACRO_RECORD_LED.read_text().strip()) > 0
    except Exception:
        return False


def load_macros():
    if MACROS_FILE.exists():
        try:
            return json.loads(MACROS_FILE.read_text())
        except Exception:
            pass
    return {"M1": {}, "M2": {}, "M3": {}}


def save_macro(profile, gkey, value, kind="keys"):
    """kind is 'keys' (a ydotool key-sequence string) or 'command' (a
    shell command string). Stored as {"type": ..., "value": ...} --
    g510_macro_daemon.py checks 'type' to decide how to replay it."""
    macros = load_macros()
    macros.setdefault(profile, {})[gkey] = {"type": kind, "value": value}
    MACROS_FILE.write_text(json.dumps(macros, indent=2))


def clear_macro(profile, gkey):
    macros = load_macros()
    macros.setdefault(profile, {}).pop(gkey, None)
    MACROS_FILE.write_text(json.dumps(macros, indent=2))


class RecorderThread(QThread):
    """Captures real keystrokes from the main keyboard while recording,
    grabbing the device so they don't also leak into whatever window has
    focus. Emits the final ydotool-ready 'code:value code:value ...'
    string when stopped, plus an ok flag -- same convention as
    ImageResizeWorker's finished_resize(..., bool) below, not a
    separate error signal.

    Real bug found via direct reproduction (crashed the whole process,
    SIGABRT, twice): evdev.InputDevice(MAIN_KEYBOARD_DEVICE) used to run
    unguarded -- if the keyboard isn't plugged in (or MAIN_KEYBOARD_DEVICE
    is ever stale), the exception escaped this QThread.run() entirely,
    which PyQt5 does not route through Python's normal exception
    handling -- it aborts the process. ImageResizeWorker (added later,
    see its own docstring) already wraps its whole run() in try/except
    for exactly this reason; this thread predates that pattern and
    never got the same treatment."""
    finished_recording = pyqtSignal(str, bool)  # sequence, ok

    def __init__(self):
        super().__init__()
        self._stop = False
        self._events = []

    def stop(self):
        self._stop = True

    def run(self):
        import select
        try:
            dev = evdev.InputDevice(MAIN_KEYBOARD_DEVICE)
            dev.grab()
        except OSError:
            self.finished_recording.emit("", False)
            return
        try:
            while not self._stop:
                # Poll with a short timeout instead of a blocking read --
                # read_loop() only checks _stop between events, so it can
                # hang forever if the user stops without pressing another
                # key. This checks _stop every 0.1s regardless.
                r, _, _ = select.select([dev.fd], [], [], 0.1)
                if not r:
                    continue
                for event in dev.read():
                    if event.type == ecodes.EV_KEY:
                        self._events.append(f"{event.code}:{event.value}")
        finally:
            dev.ungrab()
            dev.close()
        self.finished_recording.emit(" ".join(self._events), True)


class MacroRecordDialog(QDialog):
    def __init__(self, profile, gkey, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.gkey = gkey
        self.recorder = None
        self.recorded_sequence = None

        self.setWindowTitle(f"{profile} / {gkey}")
        layout = QVBoxLayout()

        macros = load_macros()
        existing = macros.get(profile, {}).get(gkey)
        if isinstance(existing, dict) and existing.get("type") == "command":
            status_text = f"Führt aktuell aus: {existing.get('value', '')}"
        elif existing:
            status_text = "Aktuell belegt (aufgezeichnete Tastenfolge)."
        else:
            status_text = "Noch nichts zugewiesen."
        self.status_label = QLabel(status_text)
        layout.addWidget(self.status_label)

        self.record_btn = QPushButton("Aufnehmen")
        self.record_btn.setToolTip("Aufnahme einer Tastenfolge starten – erneut klicken zum Beenden")
        self.record_btn.clicked.connect(self.toggle_recording)
        layout.addWidget(self.record_btn)

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Speichern")
        self.save_btn.setToolTip("Aufgezeichnete Tastenfolge auf dieser G-Taste speichern")
        self.save_btn.clicked.connect(self.on_save)
        self.save_btn.setEnabled(False)
        clear_btn = QPushButton("Löschen")
        clear_btn.setToolTip("Aktuelle Belegung dieser G-Taste entfernen")
        clear_btn.clicked.connect(self.on_clear)
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.setToolTip("Schließen, ohne die Belegung dieser G-Taste zu ändern")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        layout.addWidget(QLabel("<b>Oder stattdessen einen Befehl ausführen:</b>"))
        cmd_row = QHBoxLayout()
        self.command_edit = QLineEdit()
        self.command_edit.setPlaceholderText("z. B. notify-send hello")
        self.command_edit.setToolTip("Beliebiger Shell-Befehl, der beim Drücken dieser G-Taste ausgeführt wird, statt Tasten abzuspielen")
        if isinstance(existing, dict) and existing.get("type") == "command":
            self.command_edit.setText(existing.get("value", ""))
        save_cmd_btn = QPushButton("Befehl speichern")
        save_cmd_btn.setToolTip("Diesen Shell-Befehl auf dieser G-Taste speichern")
        save_cmd_btn.clicked.connect(self.on_save_command)
        cmd_row.addWidget(self.command_edit)
        cmd_row.addWidget(save_cmd_btn)
        layout.addLayout(cmd_row)

        self.setLayout(layout)

    def toggle_recording(self):
        if self.recorder is None:
            self.status_label.setText("Aufnahme läuft … Tastenkombination drücken, dann auf Stopp klicken.")
            self.record_btn.setText("Stopp")
            self.recorder = RecorderThread()
            self.recorder.finished_recording.connect(self.on_recorded)
            self.recorder.start()
        else:
            self.record_btn.setEnabled(False)  # ignore clicks until the thread actually finishes
            self.status_label.setText("Wird beendet …")
            self.recorder.stop()

    def reject(self):
        if self.recorder is not None:
            self.recorder.stop()
            self.recorder.wait(2000)  # let it clean up (ungrab) before the dialog closes
        super().reject()

    def on_recorded(self, sequence, ok):
        self.recorded_sequence = sequence
        if self.recorder is not None:
            # The signal can arrive just before Qt finishes tearing down
            # the OS thread -- wait() blocks until that's truly done
            # before we drop the last Python reference. Skipping this
            # causes "QThread: Destroyed while thread is still running"
            # and a hard process abort (confirmed -- this crashed twice).
            self.recorder.wait()
        self.recorder = None
        self.record_btn.setText("Aufnehmen")
        self.record_btn.setEnabled(True)
        if not ok:
            self.status_label.setText("Tastatur nicht gefunden – ist sie angeschlossen?")
            self.save_btn.setEnabled(False)
            return
        self.status_label.setText(f"{len(sequence.split())} Ereignisse erfasst. Zum Behalten auf Speichern klicken.")
        self.save_btn.setEnabled(bool(sequence))

    def on_save(self):
        if self.recorded_sequence:
            save_macro(self.profile, self.gkey, self.recorded_sequence, kind="keys")
        self.accept()

    def on_save_command(self):
        cmd = self.command_edit.text().strip()
        if cmd:
            save_macro(self.profile, self.gkey, cmd, kind="command")
        self.accept()

    def on_clear(self):
        clear_macro(self.profile, self.gkey)
        self.accept()


class KeyboardTab(QWidget):
    """Unified Backlight + G-Keys view: a real keyboard-shaped canvas
    (see g510_canvas.py) next to a control panel, same overall pattern
    as the sibling G910 app's canvas+sidebar layout -- adapted here for
    a single-zone backlight (one live color for the whole board, not
    per-key) and 18 G-keys instead of 9.

    G-keys on the canvas open the existing macro-record dialog
    unchanged; M1/M2/M3 switch the active profile unchanged; a poll
    timer keeps the canvas's active-M-key highlight and MR indicator in
    sync with the daemon/hardware, exactly like the old GKeysTab did."""
    def __init__(self):
        super().__init__()
        self.current_profile = "M1"

        root = QHBoxLayout()

        canvas_col = QVBoxLayout()
        self.canvas = g510_canvas.G510Canvas()
        current_rgb = read_current_rgb()
        if current_rgb:
            self.canvas.set_board_color(QColor(*current_rgb))
        self.canvas.gkey_clicked.connect(self.open_key_dialog)
        self.canvas.mkey_clicked.connect(self.select_profile)
        self.refresh_assigned_keys()
        canvas_col.addWidget(self.canvas)

        hint = QLabel("G-Taste anklicken, um ein Makro aufzunehmen  •  M1/M2/M3 anklicken, um das Profil zu wechseln  •  goldener Rahmen = Makro zugewiesen")
        hint.setObjectName("Status")
        hint.setWordWrap(True)
        canvas_col.addWidget(hint)
        canvas_col.addStretch()
        root.addLayout(canvas_col, stretch=1)

        panel = QWidget()
        panel.setObjectName("Panel")
        panel.setFixedWidth(220)
        panel_layout = QVBoxLayout()

        title = QLabel("Beleuchtung")
        title.setObjectName("Title")
        panel_layout.addWidget(title)
        try:
            standard_rgb = game_colors.load_standard_color(DEFAULTS_SCRIPT_DATA_DIR)
        except (OSError, ValueError) as error:
            standard_rgb = None
            warning = QLabel(f"Standardfarbe konnte nicht geladen werden: {error}")
            warning.setWordWrap(True)
            panel_layout.addWidget(warning)

        # Swatch-grid + hex-entry picker, matching the sibling G910
        # app's own picker (direct request: "a colour picker like you
        # did for g910") -- replaces the old plain dropdown. Doesn't
        # apply anything by itself; sets self._pending_rgb, which the
        # existing Apply/Set as Default buttons below act on, keeping
        # G510s's own already-working live/persist distinction (G910's
        # picker has no separate "default" concept to preserve).
        self._pending_rgb = standard_rgb or current_rgb or next(iter(COLOR_RGB.values()))

        panel_layout.addWidget(QLabel("Farbe"))
        self.preview_swatch = QLabel()
        self.preview_swatch.setFixedHeight(26)
        self._set_preview_style(self._pending_rgb)
        panel_layout.addWidget(self.preview_swatch)

        panel_layout.addSpacing(6)
        panel_layout.addWidget(QLabel("<b>Hex-Code</b>"))
        hex_row = QHBoxLayout()
        self.hex_edit = QLineEdit()
        self.hex_edit.setPlaceholderText("8000ff")
        self.hex_edit.setToolTip("6-stellige Hex-Farbe, ohne # eingeben")
        self.hex_edit.returnPressed.connect(self.on_apply_hex)
        hex_apply_btn = QPushButton("Übernehmen")
        hex_apply_btn.setToolTip("Diese Hex-Farbe auf der Zeichenfläche in der Vorschau zeigen (mit dem großen Anwenden-Button unten an die Tastatur senden)")
        hex_apply_btn.setObjectName("PanelPrimary")
        hex_apply_btn.clicked.connect(self.on_apply_hex)
        hex_row.addWidget(self.hex_edit)
        hex_row.addWidget(hex_apply_btn)
        panel_layout.addLayout(hex_row)

        panel_layout.addSpacing(8)
        panel_layout.addWidget(QLabel("Voreinstellungen"))
        swatch_grid = QGridLayout()
        swatch_grid.setSpacing(4)
        for i, (name, rgb) in enumerate(COLOR_RGB.items()):
            swatch_btn = QPushButton()
            swatch_btn.setToolTip(name)
            swatch_btn.setFixedSize(28, 28)
            hexval = "#%02x%02x%02x" % rgb
            swatch_btn.setStyleSheet(
                f"background-color: {hexval}; border: 1px solid #34343a; border-radius: 4px;"
            )
            swatch_btn.clicked.connect(lambda _, c=rgb: self.set_pending_color(c))
            swatch_grid.addWidget(swatch_btn, i // 3, i % 3)
        swatch_row = QHBoxLayout()
        swatch_row.addStretch()
        swatch_row.addLayout(swatch_grid)
        swatch_row.addStretch()
        panel_layout.addLayout(swatch_row)
        panel_layout.addSpacing(4)

        apply_btn = QPushButton("Anwenden")
        apply_btn.setToolTip("Diese Farbe sofort an die Tastatur senden und als Start-Standard speichern")
        apply_btn.setObjectName("PanelPrimary")
        apply_btn.clicked.connect(self.on_apply)
        panel_layout.addWidget(apply_btn)
        set_default_btn = QPushButton("Als Standard festlegen")
        set_default_btn.setToolTip("Diese Farbe als Start-Standard speichern, OHNE die aktuelle Tastaturfarbe zu ändern")
        set_default_btn.setObjectName("PanelButton")
        set_default_btn.clicked.connect(self.on_set_as_default)
        panel_layout.addWidget(set_default_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("Separator")
        panel_layout.addSpacing(10)
        panel_layout.addWidget(sep)
        panel_layout.addSpacing(10)

        service_label = QLabel("Dienste")
        service_label.setObjectName("Status")
        panel_layout.addWidget(service_label)
        service_row = QHBoxLayout()
        service_row.setSpacing(4)
        service_tooltips = {
            "start": "G510-Dienste für LCD, Tasten, Makros und Beleuchtung starten",
            "stop": "G510-Dienste beenden; die gespeicherte Standardfarbe wird wiederhergestellt",
            "restart": "G510-Dienste einschließlich der Spielfarben neu starten",
        }
        for label, action in (("Starten", "start"), ("Stoppen", "stop"), ("Neustart", "restart")):
            btn = QPushButton(label)
            btn.setObjectName("Discreet")
            btn.setToolTip(service_tooltips[action])
            btn.clicked.connect(lambda _, a=action: self.on_service_action(a))
            service_row.addWidget(btn)
        panel_layout.addLayout(service_row)

        panel_layout.addStretch()
        panel.setLayout(panel_layout)
        root.addWidget(panel)

        self.setLayout(root)

        # Physical M1/M2/M3 presses and the MR LED are hardware/daemon
        # state this GUI doesn't own -- poll and reflect them, same
        # pattern as the old GKeysTab's profile poll timer.
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_hardware_state)

        # Live-mirrors whatever's actually showing on the physical LCD
        # into the canvas's LCD cell. Separate, much slower timer than
        # poll_hardware_state above -- this one shells out to the real
        # C binary each tick (render_preview()), so 500ms would mean 2
        # subprocess spawns/sec for a screen that doesn't need to be
        # that responsive; 2s roughly matches the real stats refresh
        # cadence (see G510_README.md) instead.
        self.lcd_mirror_timer = QTimer(self)
        self.lcd_mirror_timer.timeout.connect(self.refresh_lcd_mirror)

    def showEvent(self, event):
        super().showEvent(event)
        self.poll_timer.start(500)
        self.lcd_mirror_timer.start(2000)
        self.poll_hardware_state()
        self.refresh_lcd_mirror()

    def hideEvent(self, event):
        self.poll_timer.stop()
        self.lcd_mirror_timer.stop()
        super().hideEvent(event)

    def select_profile(self, name):
        self.current_profile = name
        self.canvas.set_active_mkey(name)
        self.refresh_assigned_keys()
        # Real bug, found via live use: clicking M1/M2/M3 here used to
        # be GUI-only -- the daemon (which decides what a physical
        # G-key press actually replays) never learned about it, and
        # the poll below would revert the highlight right back within
        # 500ms. Writing the same file the daemon itself writes makes
        # this a real profile switch, not a cosmetic one -- and makes
        # this call idempotent when poll_hardware_state calls it after
        # reading an unchanged file (same value written back, harmless).
        try:
            active_profile_file().write_text(name)
        except Exception:
            pass  # matches the daemon's own best-effort LED write

    def refresh_assigned_keys(self):
        """Which G-keys have a macro in the CURRENT profile -- drawn
        with a gold border on the canvas so it's visible at a glance,
        without opening each key's dialog to check."""
        assigned = load_macros().get(self.current_profile, {}).keys()
        self.canvas.set_assigned_keys(assigned)

    def refresh_lcd_mirror(self):
        """Renders whatever screen is actually active right now
        (read_active_screen_num()) and pushes it into the canvas's LCD
        cell -- same render_preview() the Custom Screens editor uses,
        so this is provably pixel-identical to the real hardware, not
        a guess. A render failure (binary not built yet, transient
        error) just leaves the canvas showing its last good frame (or
        the placeholder, before the first one) rather than clearing it
        -- a missed tick shouldn't blank a screen that was fine a
        moment ago."""
        pixmap, _bounds, err = render_preview(read_active_screen_num(), tag="canvas")
        if pixmap is not None:
            self.canvas.set_lcd_pixmap(pixmap)

    def poll_hardware_state(self):
        try:
            live = active_profile_file().read_text().strip()
        except Exception:
            live = None
        if live in ("M1", "M2", "M3") and live != self.current_profile:
            self.select_profile(live)
        self.canvas.set_mr_active(read_macro_record_led())

    def open_key_dialog(self, gkey):
        dlg = MacroRecordDialog(self.current_profile, gkey, self)
        dlg.exec_()
        self.refresh_assigned_keys()  # a macro may have been saved or cleared

    def _set_preview_style(self, rgb):
        hexval = "#%02x%02x%02x" % rgb
        self.preview_swatch.setStyleSheet(
            f"background-color: {hexval}; border: 1px solid #34343a; border-radius: 4px;"
        )

    def set_pending_color(self, rgb):
        """Updates the preview swatch + what Apply/Set as Default will
        act on -- does NOT touch the live backlight itself. Called by
        clicking a preset swatch or a valid hex Apply, same as G910's
        picker, but G510s keeps its own separate live/persist step
        rather than applying instantly on every click."""
        self._pending_rgb = rgb
        self._set_preview_style(rgb)

    def on_apply_hex(self):
        """Exact-value path alongside the presets, for anyone who
        already knows the hex they want or wants to match a color
        precisely rather than pick from the fixed preset list."""
        text = self.hex_edit.text().strip().lstrip("#")
        if len(text) != 6 or any(c not in "0123456789abcdefABCDEF" for c in text):
            QMessageBox.critical(self, "Ungültige Farbe", "6 Hex-Ziffern verwenden, z. B. 8000ff")
            return
        rgb = tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))
        self.set_pending_color(rgb)

    def on_apply(self):
        ok, err = apply_backlight(self._pending_rgb)
        if not ok:
            QMessageBox.critical(self, "Fehler", err)
            return
        self.canvas.set_board_color(QColor(*self._pending_rgb))

    def on_set_as_default(self):
        ok, err = set_as_default(self._pending_rgb)
        if not ok:
            QMessageBox.critical(self, "Fehler", err)

    def on_service_action(self, action):
        ok, err = run_systemctl(action)
        if not ok:
            QMessageBox.critical(self, "Fehler", err)


CUSTOM_SCREENS_PANEL_WIDTH = 290
CUSTOM_SCREENS_PANEL_MAX_WIDTH = 420
ELEMENT_ROW_FIELD_WIDTH = 126

CUSTOM_SCREEN_IMAGES_DIR = DATA_DIR / "custom_screen_images"
GAME_DASHBOARD_FILE = DATA_DIR / "game_dashboard_positions.txt"


def load_custom_screens():
    return layout_store.load_custom_screens(CUSTOM_SCREENS_FILE, load_screens())


def save_custom_screens(config):
    layout_store.save_custom_screens(config, CUSTOM_SCREENS_FILE)


def load_game_dashboard_offsets():
    return layout_store.load_game_dashboard_offsets(GAME_DASHBOARD_FILE)


def save_game_dashboard_offsets(offsets):
    layout_store.save_game_dashboard_offsets(offsets, GAME_DASHBOARD_FILE)


def render_preview(screen_num, tag="app", editor=False):
    return preview_renderer.render_preview(STATS_BINARY, screen_num, tag, editor)


class ImageResizeWorker(QThread):
    """Runs png-to-lcd.py's conversion off the GUI thread. Direct
    finding from a self-audit: doing this subprocess call synchronously
    inside the 120ms drag_refresh_timer tick was measured (not assumed)
    at ~85-90ms per call -- meaning the UI thread was blocked roughly
    75% of the time while actively dragging an image's resize handle.
    Same QThread pattern already used for macro recording (see
    RecorderThread above) -- the app already trusts this approach for
    keeping the UI responsive during slower work."""
    finished_resize = pyqtSignal(int, int, int, bool)  # index, width, height, ok

    def __init__(self, index, src_path, out_path, target_w, target_h, png_to_lcd_path):
        super().__init__()
        self.index = index
        self.src_path = src_path
        self.out_path = out_path
        self.target_w = target_w
        self.target_h = target_h
        self.png_to_lcd_path = png_to_lcd_path

    def run(self):
        try:
            result = subprocess.run(
                [sys.executable, str(self.png_to_lcd_path), str(self.src_path), str(self.out_path),
                 str(self.target_w), str(self.target_h)],
                capture_output=True, text=True, timeout=15,
            )
        except Exception:
            self.finished_resize.emit(self.index, 0, 0, False)
            return
        if result.returncode != 0:
            self.finished_resize.emit(self.index, 0, 0, False)
            return
        try:
            w, h = (int(x) for x in result.stdout.split())
        except ValueError:
            self.finished_resize.emit(self.index, 0, 0, False)
            return
        self.finished_resize.emit(self.index, w, h, True)


class CustomScreensTab(QWidget):
    """AIDA64-style dashboard builder for LCD screens. Pick a
    screen, add sensors with a display style, drag them into place on
    the live preview -- the preview is the real LCD-drawing code
    running in a one-shot mode, so what you see here is exactly what
    the keyboard will show."""
    screens_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.current_screen = "L2"
        self.config = load_custom_screens()
        self.game_dashboard_offsets = load_game_dashboard_offsets()
        self._game_dashboard_elements = {}
        self._element_rows = []
        self._design_index = 0

        root = QHBoxLayout()
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(16)

        canvas_col = QVBoxLayout()
        canvas_col.setSpacing(12)

        selector_row = QHBoxLayout()
        self.screen_combo = QComboBox()
        self.screen_combo.setMinimumWidth(180)
        self.screen_combo.setToolTip("Bildschirm im Editor und auf der Tastatur auswählen")
        self.screen_combo.activated.connect(
            lambda: self.select_screen(self.screen_combo.currentData()))
        selector_row.addWidget(self.screen_combo, 1)
        canvas_col.addLayout(selector_row)
        management_row = QHBoxLayout()
        new_screen = QPushButton("Neuer Screen…")
        new_screen.clicked.connect(self.add_screen)
        management_row.addWidget(new_screen)
        self.rename_screen_btn = QPushButton("Umbenennen…")
        self.rename_screen_btn.clicked.connect(self.rename_screen)
        management_row.addWidget(self.rename_screen_btn)
        self.delete_screen_btn = QPushButton("Löschen…")
        self.delete_screen_btn.clicked.connect(self.delete_screen)
        management_row.addWidget(self.delete_screen_btn)
        self.refresh_screen_choices()
        canvas_col.addLayout(management_row)
        self.clock_layout_row = QWidget()
        clock_row = QHBoxLayout(self.clock_layout_row)
        clock_row.setContentsMargins(0, 0, 0, 0)
        clock_row.addWidget(QLabel("Uhr-Design:"))
        previous_clock = QPushButton("Zurück")
        previous_clock.clicked.connect(lambda: self.cycle_clock_layout(-1))
        clock_row.addWidget(previous_clock)
        self.clock_layout_combo = QComboBox()
        for index, name in enumerate(CLOCK_LAYOUTS):
            self.clock_layout_combo.addItem(f"{index + 1:02d} / {len(CLOCK_LAYOUTS)} · {name}", index)
        self.clock_layout_combo.activated.connect(self.on_clock_layout_selected)
        clock_row.addWidget(self.clock_layout_combo, 1)
        next_clock = QPushButton("Weiter")
        next_clock.clicked.connect(lambda: self.cycle_clock_layout(1))
        clock_row.addWidget(next_clock)
        self.clock_layout_row.hide()
        canvas_col.addWidget(self.clock_layout_row)
        self.design_row = QWidget()
        design_row = QHBoxLayout(self.design_row)
        design_row.setContentsMargins(0, 0, 0, 0)
        design_row.addWidget(QLabel("Screen-Design:"))
        previous_design = QPushButton("Zurück")
        previous_design.clicked.connect(lambda: self.cycle_screen_design(-1))
        design_row.addWidget(previous_design)
        self.design_combo = QComboBox()
        self.design_combo.activated.connect(self.on_screen_design_selected)
        design_row.addWidget(self.design_combo, 1)
        next_design = QPushButton("Weiter")
        next_design.clicked.connect(lambda: self.cycle_screen_design(1))
        design_row.addWidget(next_design)
        canvas_col.addWidget(self.design_row)
        self.populate_design_choices()
        device_grid = QGridLayout()
        device_grid.setHorizontalSpacing(12)
        device_grid.setVerticalSpacing(10)
        cycle_button = QPushButton("L1\nWeiter")
        cycle_button.setFixedWidth(96)
        cycle_button.setMinimumHeight(60)
        cycle_button.clicked.connect(self.cycle_preview)
        cycle_button.setToolTip("Nächsten Bildschirm im Editor und auf dem LCD anzeigen.")
        device_grid.addWidget(cycle_button, 0, 0, Qt.AlignVCenter)
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(10)
        self.function_buttons = {}
        self.function_menu_buttons = {}
        self.key_bindings = None
        for key in ("L2", "L3", "L4", "L5"):
            button = QPushButton(key)
            button.setMinimumHeight(46)
            button.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            button.clicked.connect(lambda checked=False, current_key=key:
                                   self.execute_function_binding(current_key))
            menu_button = QPushButton("Belegung ändern")
            menu_button.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            menu_button.setToolTip(f"Aktion für {key} auswählen, ohne sie auszuführen.")
            menu = QMenu(menu_button)
            menu.aboutToShow.connect(
                lambda current_key=key: self.populate_function_menu(current_key))
            menu_button.setMenu(menu)
            column = QVBoxLayout()
            column.setSpacing(5)
            column.addWidget(button)
            column.addWidget(menu_button)
            buttons_row.addLayout(column, 1)
            self.function_buttons[key] = button
            self.function_menu_buttons[key] = menu_button

        # Painting and hit testing share the same aspect-preserving transform.
        self.preview_canvas = ScreenPreviewCanvas()
        self.preview_canvas.element_moved.connect(self.on_element_dragged)
        self.preview_canvas.element_resized.connect(self.on_element_resized)
        self.preview_canvas.image_resize_requested.connect(self.on_image_resize_requested)
        self.preview_canvas.element_hovered.connect(self.on_preview_element_hovered)
        self.preview_canvas.drag_started.connect(self.on_drag_started)
        self.preview_canvas.drag_finished.connect(self.on_drag_finished)
        # Image-resize regen runs on a background ImageResizeWorker (see
        # class above) instead of blocking the GUI thread every timer
        # tick. At most one worker is ever in flight per drag -- a newer
        # request that arrives while one is still running is coalesced
        # into _image_resize_next rather than spawning overlapping
        # subprocesses; _image_resize_screen guards against a result
        # landing on the wrong screen if you somehow switch screens
        # while one is in flight. _image_resize_el is the actual element
        # dict object the worker was started for -- a real self-audit
        # bug: removing a different element earlier in the list while a
        # resize was in flight could shift a surviving element into the
        # same index, silently misapplying the resize to it. Checking
        # identity (`elements[index] is el_token`), not just the index
        # bound, is what actually closes that.
        self._image_resize_worker = None
        self._image_resize_next = None
        self._image_resize_screen = None
        self._image_resize_el = None
        device_grid.addWidget(self.preview_canvas, 0, 1)
        device_grid.addLayout(buttons_row, 1, 1)
        device_grid.setColumnStretch(1, 1)
        device_grid.setRowStretch(0, 1)
        canvas_col.addLayout(device_grid, 1)

        self.drag_hint = QLabel(
            "Alles per Ziehen verschieben. Mit der Maus über einen Balken oder ein frisch "
            "importiertes Bild fahren, um den Größengriff anzuzeigen."
        )
        self.drag_hint.setWordWrap(True)
        self.drag_hint.setObjectName("Status")
        canvas_col.addWidget(self.drag_hint)
        root.addLayout(canvas_col, stretch=1)

        panel = QWidget()
        panel.setObjectName("Panel")
        panel.setMinimumWidth(CUSTOM_SCREENS_PANEL_WIDTH)
        panel_layout = QVBoxLayout()
        panel_layout.setContentsMargins(14, 14, 14, 14)
        panel_layout.setSpacing(8)

        title = QLabel("LCD-Bildschirme")
        title.setObjectName("Title")
        panel_layout.addWidget(title)

        add_section = QLabel("Element hinzufügen")
        add_section.setObjectName("PanelSection")
        panel_layout.addWidget(add_section)
        self.sensor_combo = QComboBox()
        self.sensor_combo.setToolTip("Welcher Wert/Sensor zu diesem Bildschirm hinzugefügt wird – nach der Auswahl erscheint unten eine Beschreibung")
        for key, label in SENSOR_CHOICES:
            self.sensor_combo.addItem(label, key)
        self.sensor_combo.currentIndexChanged.connect(self.on_sensor_changed)
        panel_layout.addWidget(self.sensor_combo)

        # Direct feedback: "i dont know from that list what is what
        # and exactly what they do" -- live one-line explanation of
        # whatever's currently selected, not just a label to guess at.
        self.sensor_desc_label = QLabel("")
        self.sensor_desc_label.setObjectName("Status")
        self.sensor_desc_label.setWordWrap(True)
        panel_layout.addWidget(self.sensor_desc_label)

        self.style_combo = QComboBox()
        self.style_combo.setToolTip("Zahl: Rohwert als Text. Balken: Prozentwerte/Temperaturen. Verlauf: letzte 60 Messwerte für Netzwerk-Download oder -Upload.")
        self.style_combo.addItem("Zahl", "number")
        self.style_combo.addItem("Balken", "bar")
        self.style_combo.addItem("Verlauf", "history")
        self.style_combo.addItem("Füllbalken mit Wert", "gauge")
        self.style_combo.currentIndexChanged.connect(self.on_style_changed)

        self.orientation_label = QLabel("Balkenausrichtung:")
        self.orientation_label.setToolTip(
            "Senkrechte Balken zeigen eine kompakte Beschriftung über der Füllung; Größe per Ziehen am unteren Griff ändern."
        )
        self.orientation_combo = QComboBox()
        self.orientation_combo.addItem("Waagerecht", "horizontal")
        self.orientation_combo.addItem("Senkrecht", "vertical")

        # Direct request: "id like to be able to resize elements".
        # Shared between new sensor elements and new text elements --
        # both just render through g15r_renderString at whatever size
        # this picks (see FONT_SIZE_CHOICES). Applies to the sensor's
        # VALUE only; the label always stays the fixed custom font.
        display_options = QGridLayout()
        display_options.setHorizontalSpacing(10)
        display_options.setVerticalSpacing(4)
        display_options.addWidget(QLabel("Anzeigestil:"), 0, 0)
        display_options.addWidget(QLabel("Textgröße:"), 0, 1)
        display_options.addWidget(self.style_combo, 1, 0)
        self.font_size_combo = QComboBox()
        self.font_size_combo.setToolTip("Größe des Werttextes dieses Elements nach dem Hinzufügen (Groß/Riesig sind beim Balkenstil deaktiviert – neben dem Balken ist kein Platz)")
        for value, label in FONT_SIZE_CHOICES:
            self.font_size_combo.addItem(label, value)
        display_options.addWidget(self.font_size_combo, 1, 1)
        panel_layout.addLayout(display_options)

        orientation_row = QHBoxLayout()
        orientation_row.setContentsMargins(0, 0, 0, 0)
        orientation_row.addWidget(self.orientation_label)
        orientation_row.addWidget(self.orientation_combo, stretch=1)
        panel_layout.addLayout(orientation_row)

        self.bar_hint_label = QLabel(
            "Für diesen Sensor gibt es keine sinnvolle 0–100-Skala – wird als Zahl angezeigt."
        )
        self.bar_hint_label.setObjectName("Status")
        self.bar_hint_label.setWordWrap(True)
        self.bar_hint_label.hide()
        panel_layout.addWidget(self.bar_hint_label)
        # connect() above ran before this label existed, and Qt doesn't
        # retroactively fire currentIndexChanged for an already-selected
        # index -- populate the description for the startup selection.
        self.on_sensor_changed()

        self.add_btn = add_btn = QPushButton("Hinzufügen")
        add_btn.setToolTip("Den gewählten Sensor zu diesem Bildschirm hinzufügen – danach an die richtige Stelle ziehen")
        add_btn.setObjectName("PanelPrimary")
        add_btn.clicked.connect(self.on_add_element)
        panel_layout.addWidget(add_btn)

        self.layout_preset_combo = QComboBox()
        self.layout_preset_combo.addItem("CPU-/GPU-Auslastung", "performance")
        self.layout_preset_combo.addItem("Temperaturübersicht", "temperatures")
        self.layout_preset_combo.addItem("Systemübersicht", "system")
        self.layout_preset_combo.addItem(PRESET_NAMES["network"], "network")
        self.layout_preset_combo.addItem("Medienwiedergabe", "media")
        self.layout_preset_combo.setToolTip("Wähle eine fertige Vorlage für den ausgewählten LCD-Bildschirm.")
        panel_layout.addWidget(self.layout_preset_combo)
        self.apply_layout_btn = QPushButton("Vorlage anwenden...")
        self.apply_layout_btn.setObjectName("PanelButton")
        self.apply_layout_btn.setToolTip(
            "Ersetzt den ausgewählten Bildschirm durch eine Vorlage. "
            "Alle Elemente lassen sich anschließend verschieben und bearbeiten."
        )
        self.apply_layout_btn.clicked.connect(self.on_apply_layout_preset)
        panel_layout.addWidget(self.apply_layout_btn)

        self.apply_default_btn = QPushButton("Standardlayouts wiederherstellen")
        self.apply_default_btn.setObjectName("PanelButton")
        self.apply_default_btn.setToolTip(
            "Systemübersicht, Medien, Temperaturen und Netzwerkverbindung. "
            "Die Funktionstastenbelegung bleibt unverändert.")
        self.apply_default_btn.clicked.connect(self.on_apply_default_layout)
        panel_layout.addWidget(self.apply_default_btn)

        profile_row = QHBoxLayout()
        self.profile_combo = QComboBox()
        for pname in PROFILES:
            self.profile_combo.addItem(pname)
        self.profile_combo.setToolTip(
            "Profil: setzt LED-Farbe (dauerhaft) und wechselt den LCD-Bildschirm.")
        profile_row.addWidget(self.profile_combo, 1)
        self.apply_profile_btn = QPushButton("Profil anwenden")
        self.apply_profile_btn.setObjectName("PanelButton")
        self.apply_profile_btn.clicked.connect(self.on_apply_profile)
        profile_row.addWidget(self.apply_profile_btn)
        panel_layout.addLayout(profile_row)

        # Direct report: "gui buttons are ambigious and not that well
        # placed" -- Import Image/Add Text/Add Visualizer were stacked
        # directly under "Add" with nothing to show they're independent
        # actions, not related to the sensor/style/size dropdowns above.
        # A visible separator + label makes the grouping unambiguous.
        elements_sep = QFrame()
        elements_sep.setFrameShape(QFrame.HLine)
        elements_sep.setObjectName("Separator")
        panel_layout.addSpacing(8)
        panel_layout.addWidget(elements_sep)
        panel_layout.addSpacing(4)
        other_elements_label = QLabel("Weitere Elemente:")
        other_elements_label.setObjectName("PanelSection")
        panel_layout.addWidget(other_elements_label)

        self.import_image_btn = QPushButton("Bild importieren...")
        self.import_image_btn.setToolTip("PNG/Bild importieren und automatisch in 1 Bit für diesen Bildschirm umwandeln – einfache, kontrastreiche Logos/Symbole sehen am besten aus, siehe G510_README.md")
        self.import_image_btn.setObjectName("PanelButton")
        self.import_image_btn.clicked.connect(self.on_import_image)
        panel_layout.addWidget(self.import_image_btn)

        self.add_text_btn = QPushButton("Text hinzufügen...")
        self.add_text_btn.setToolTip("Kurze freie Beschriftung hinzufügen (z. B. ein Trenner oder eine feste Bezeichnung)")
        self.add_text_btn.setObjectName("PanelButton")
        self.add_text_btn.clicked.connect(self.on_add_text)
        panel_layout.addWidget(self.add_text_btn)

        self.add_frame_btn = QPushButton("Rahmen hinzufügen")
        self.add_frame_btn.setObjectName("PanelButton")
        self.add_frame_btn.clicked.connect(self.on_add_frame)
        panel_layout.addWidget(self.add_frame_btn)

        self.add_visualizer_btn = QPushButton("Visualizer hinzufügen")
        self.add_visualizer_btn.setObjectName("PanelButton")
        self.add_visualizer_btn.setToolTip(
            "Ein Live-Audio-Balkenvisualizer – reagiert auf alles, was gerade "
            "auf diesem PC läuft (jeder Player: Brave, Spotify, VLC usw.)."
        )
        self.add_visualizer_btn.clicked.connect(self.on_add_visualizer)
        panel_layout.addWidget(self.add_visualizer_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("Separator")
        panel_layout.addSpacing(6)
        panel_layout.addWidget(sep)
        panel_layout.addSpacing(6)

        # Recovery for the drag-clamp bug: an element dragged before
        # this fix could have its content still hanging off the visible
        # screen edge, with its now off-screen hit-box making it hard
        # to grab back. Only shown when something's actually off-screen.
        self.fix_overflow_btn = QPushButton("Elemente außerhalb zurückholen")
        self.fix_overflow_btn.setToolTip("Holt jedes Element, dessen Inhalt über den sichtbaren Bildschirmrand hinausragt, zurück ins Bild")
        self.fix_overflow_btn.setObjectName("PanelButton")
        self.fix_overflow_btn.clicked.connect(self.on_fix_overflow)
        self.fix_overflow_btn.hide()
        panel_layout.addWidget(self.fix_overflow_btn)

        elements_section = QLabel("Elemente auf diesem Bildschirm")
        elements_section.setObjectName("PanelSection")
        panel_layout.addWidget(elements_section)
        # Keine eigene Scrollleiste: die Liste wächst mit, das ganze Panel
        # scrollt nur bei Bedarf.
        elements_container = QWidget()
        self.elements_layout = QVBoxLayout()
        self.elements_layout.setSpacing(2)
        self.elements_layout.setContentsMargins(0, 0, 0, 0)
        self.elements_layout.addStretch()
        elements_container.setLayout(self.elements_layout)
        panel_layout.addWidget(elements_container, stretch=1)
        panel.setLayout(panel_layout)
        self.editor_panel = panel
        # Das ganze Panel scrollt, wenn das Fenster zu niedrig ist, und
        # darf bei breiten Fenstern etwas wachsen.
        panel_scroll = QScrollArea()
        panel_scroll.setWidgetResizable(True)
        panel_scroll.setFrameShape(QFrame.NoFrame)
        panel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        panel_scroll.setMinimumWidth(CUSTOM_SCREENS_PANEL_WIDTH + 18)
        panel_scroll.setMaximumWidth(CUSTOM_SCREENS_PANEL_MAX_WIDTH)
        panel_scroll.setWidget(panel)
        root.addWidget(panel_scroll)

        self.setLayout(root)

        self.on_sensor_changed()
        self.refresh_elements_list()
        self.refresh_function_buttons()
        self.refresh_preview()

        # Keeps the preview live (matches the real daemon's own refresh
        # cadence for these screens) so it feels the same as watching
        # the actual keyboard. NOT started here -- this tab is hidden
        # behind "Backlight + G-Keys" at startup, and showEvent()
        # below is what actually starts it once it's visible (see that
        # method's comment for why this matters).
        self.preview_timer = QTimer(self)
        self.preview_timer.timeout.connect(self.refresh_preview)

        # Separate, faster timer -- only running while actively
        # dragging -- so the preview visibly follows your mouse instead
        # of waiting up to a second for the next idle tick.
        self.drag_refresh_timer = QTimer(self)
        self.drag_refresh_timer.timeout.connect(self.refresh_preview)

    def showEvent(self, event):
        # Only render while this page is visible.
        super().showEvent(event)
        self.preview_timer.start(1000)
        self.refresh_function_buttons()
        self.refresh_preview()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.preview_timer.stop()

    def refresh_screen_choices(self):
        screens = load_screens()
        self.screen_combo.clear()
        for number, name in screens.items():
            self.screen_combo.addItem(name, f"L{number}")
        self.screen_combo.setCurrentIndex(self.screen_combo.findData(self.current_screen))
        custom = int(self.current_screen[1:]) >= 6
        self.rename_screen_btn.setEnabled(custom)
        self.delete_screen_btn.setEnabled(custom)

    def request_screen_name(self, title, initial=""):
        name, accepted = QInputDialog.getText(self, title, "Name des Bildschirms:",
                                             text=initial)
        if not accepted:
            return None
        name = name.strip()
        if not name or any(ord(character) < 32 for character in name):
            raise ValueError("Bitte einen nicht leeren Namen ohne Steuerzeichen eingeben.")
        existing = load_screens()
        if any(name.casefold() == value.casefold() for number, value in existing.items()
               if initial == "" or number != self.screen_number()):
            raise ValueError("Dieser Bildschirmname ist bereits vergeben.")
        return name

    def add_screen(self):
        try:
            name = self.request_screen_name("Neuer Bildschirm")
            if name is None:
                return
            catalog = load_screen_catalog()
            number = catalog["next_id"]
            if number > 2147483647:
                raise ValueError("Der technische ID-Wertebereich ist ausgeschöpft.")
            key = f"L{number}"
            while key in self.config:
                number += 1
                key = f"L{number}"
                if number > 2147483647:
                    raise ValueError("Der technische ID-Wertebereich ist ausgeschöpft.")
            updated = {**self.config, key: []}
            save_custom_screens(updated)
            catalog["screens"].append({"id": number, "name": name})
            catalog["next_id"] = number + 1
            try:
                save_screen_catalog(catalog)
            except OSError:
                save_custom_screens(self.config)
                raise
            self.config = updated
            self.refresh_screen_choices()
            self.screens_changed.emit()
            self.select_screen(key)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Bildschirm anlegen", str(error))

    def rename_screen(self):
        if self.screen_number() < 6:
            return
        try:
            name = self.request_screen_name("Bildschirm umbenennen",
                                            load_screens()[self.screen_number()])
            if name is None:
                return
            catalog = load_screen_catalog()
            for entry in catalog["screens"]:
                if entry["id"] == self.screen_number():
                    entry["name"] = name
            save_screen_catalog(catalog)
            self.refresh_screen_choices()
            self.refresh_function_buttons()
            self.screens_changed.emit()
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Bildschirm umbenennen", str(error))

    def delete_screen(self):
        number = self.screen_number()
        if number < 6:
            return
        try:
            name = load_screens()[number]
            if QMessageBox.question(
                    self, "Bildschirm löschen",
                    f"„{name}“ und seine Layoutelemente wirklich löschen?\n"
                    "Tastenverweise auf diesen Screen werden unbelegt.",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No) != QMessageBox.Yes:
                return
            # Move off the deleted screen before removing its layout.
            if read_screen() == number:
                show_screen(2)
            old_catalog = load_screen_catalog()
            catalog = {**old_catalog, "screens": [
                entry for entry in old_catalog["screens"] if entry["id"] != number]}
            save_screen_catalog(catalog)
            updated = {key: value for key, value in self.config.items()
                       if key != self.current_screen}
            try:
                save_custom_screens(updated)
            except OSError:
                save_screen_catalog(old_catalog)
                raise
            self.config = updated
            self.current_screen = "L2"
            self.refresh_screen_choices()
            self.screens_changed.emit()
            self.select_screen("L2")
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Bildschirm löschen", str(error))

    def select_screen(self, key):
        self.current_screen = key
        self.clock_layout_row.setVisible(key == "L1")
        self.populate_design_choices()
        self.refresh_function_buttons()
        self.drag_hint.setText(
            "Während ein Spiel läuft, Logo/Titel oder CPU-/GPU-Block in der Vorschau ziehen, "
            "um das automatische Spieldashboard zu positionieren."
            if key == "L4" else
            "Das Media Center zeigt automatisch Symbol, Laufschrift, Fortschritt und Spektrum, "
            "solange hier keine eigenen Elemente liegen. Eigene Elemente ersetzen diese Ansicht."
            if key == "L3" else
            "Netzwerk: Die beiden Verläufe zeigen je 60 Messwerte mit eigener automatischer "
            "Höhenskala. Verlauf zum Verschieben ziehen, an der Ecke skalieren."
            if key == "L5" else
            "20 Uhr-Designs: Auswahl oben oder auf der Tastatur mit L2 zurück / L3 weiter "
            "(Standardbelegung). Die Auswahl bleibt gespeichert."
            if key == "L1" else
            "Alles per Ziehen verschieben. Mit der Maus über einen Balken oder ein frisch "
            "importiertes Bild fahren, um den Größengriff anzuzeigen."
        )
        index = self.screen_combo.findData(key)
        if index >= 0:
            self.screen_combo.setCurrentIndex(index)
        self.rename_screen_btn.setEnabled(int(key[1:]) >= 6)
        self.delete_screen_btn.setEnabled(int(key[1:]) >= 6)
        editable = key != "L1"
        l1_reason = "Die eingebaute Uhr lässt sich nicht bearbeiten." if not editable else ""
        self.sensor_combo.setEnabled(editable)
        self.sensor_combo.setToolTip(l1_reason)
        self.style_combo.setEnabled(editable)
        self.style_combo.setToolTip(l1_reason)
        show_orientation = editable and self.style_combo.currentData() == "bar"
        self.orientation_combo.setEnabled(show_orientation)
        self.orientation_combo.setToolTip(l1_reason)
        self.orientation_label.setVisible(show_orientation)
        self.orientation_combo.setVisible(show_orientation)
        self.add_btn.setEnabled(editable)
        self.add_btn.setToolTip(l1_reason)
        self.import_image_btn.setEnabled(editable)
        self.import_image_btn.setToolTip(l1_reason)
        self.add_text_btn.setEnabled(editable)
        self.add_text_btn.setToolTip(l1_reason)
        self.add_frame_btn.setEnabled(editable)
        self.add_frame_btn.setToolTip(l1_reason if not editable else "Rahmen am Rand verschieben oder an der Ecke skalieren.")
        self.add_visualizer_btn.setEnabled(editable)
        self.add_visualizer_btn.setToolTip(
            l1_reason if not editable else
            "Ein Live-Audio-Balkenvisualizer – reagiert auf alles, was gerade "
            "auf diesem PC läuft (jeder Player: Brave, Spotify, VLC usw.)."
        )
        self.on_style_changed()
        self.refresh_elements_list()
        self.refresh_preview()
        try:
            self.apply_selected_screen()
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Bildschirmwechsel fehlgeschlagen", str(error))

    def apply_selected_screen(self):
        screen = self.screen_number()
        show_screen(screen)
        if read_screen() != screen:
            raise OSError("Die Bildschirmwahl konnte nicht bestätigt werden.")
        return load_screens()[self.screen_number()]

    def cycle_preview(self):
        current = 1 if self.current_screen == "L1" else int(self.current_screen[1:])
        screen = next_screen(current)
        self.select_screen("L1" if screen == 1 else f"L{screen}")

    def refresh_function_buttons(self):
        screen = "1" if self.current_screen == "L1" else self.current_screen[1:]
        try:
            bindings = load_bindings()
            labels = action_labels()
        except (OSError, ValueError) as error:
            self.key_bindings = None
            for key, button in self.function_buttons.items():
                button.setText(f"{key}\nBelegungsfehler")
                button.setToolTip(
                    f"{error}\nBelegung über das Menü darunter erneut laden.")
            return
        self.key_bindings = bindings
        for key, button in self.function_buttons.items():
            button.setText(f"{key}\n{labels[bindings[screen][key]]}")
            button.setToolTip(
                f"{key}: Ausgewählte Aktion für diesen Bildschirm jetzt ausführen. "
                "Die Belegung lässt sich im Menü darunter ändern. "
                "Mediensteuerung benötigt einen MPRIS-Player.")

    def execute_function_binding(self, key):
        try:
            bindings = load_bindings()
            action = bindings[str(self.screen_number())][key]
            self.apply_selected_screen()
            perform_action(action)
            target = f"L{read_screen()}"
            if target != self.current_screen:
                self.select_screen(target)
            else:
                self.refresh_preview()
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            QMessageBox.warning(self, "LCD-Tasten", f"{key}: Aktion fehlgeschlagen: {error}")
        self.refresh_function_buttons()

    def populate_function_menu(self, key):
        menu = self.function_menu_buttons[key].menu()
        menu.clear()
        screen = self.screen_number()
        try:
            bindings = load_bindings()
            labels = action_labels()
        except (OSError, ValueError) as error:
            self.key_bindings = None
            item = menu.addAction(f"Belegung konnte nicht geladen werden: {error}")
            item.setEnabled(False)
            menu.addAction("Erneut laden", self.refresh_function_buttons)
            return
        self.key_bindings = bindings
        selected = bindings[str(screen)][key]
        for action, label in labels.items():
            item = menu.addAction(label)
            item.setData(action)
            item.setCheckable(True)
            item.setChecked(action == selected)
            item.setEnabled(
                (action not in CLOCK_ACTIONS or screen == 1) and
                (action not in DESIGN_ACTIONS or screen in SCREEN_DESIGNS))
            item.triggered.connect(
                lambda checked=False, target=action, target_screen=screen:
                self.save_function_binding(target_screen, key, target))

    def save_function_binding(self, screen, key, action):
        try:
            # Reload so editing one key cannot overwrite externally changed bindings.
            bindings = load_bindings()
            bindings[str(screen)][key] = action
            save_bindings(bindings)
        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self, "LCD-Tasten", f"Speichern fehlgeschlagen: {error}")
        self.refresh_function_buttons()

    def on_sensor_changed(self):
        sensor_key = self.sensor_combo.currentData()
        capable = sensor_key in BAR_CAPABLE_SENSORS
        self.bar_hint_label.setVisible(not capable)
        self.sensor_desc_label.setText(SENSOR_DESCRIPTIONS.get(sensor_key, ""))
        history_index = self.style_combo.findData("history")
        history_capable = sensor_key in ("NET_DOWN", "NET_UP")
        self.style_combo.model().item(history_index).setEnabled(history_capable)
        if not history_capable and self.style_combo.currentData() == "history":
            self.style_combo.setCurrentIndex(self.style_combo.findData("number"))
        self.style_combo.model().item(self.style_combo.findData("gauge")).setEnabled(capable)
        if not capable and self.style_combo.currentData() == "gauge":
            self.style_combo.setCurrentIndex(self.style_combo.findData("number"))
        self.on_style_changed()

    def on_style_changed(self):
        # Self-audit finding: Large/Huge next to a bar looks visually
        # unbalanced (the bar's own height doesn't scale). Grey those
        # two options out while "Bar" is selected instead of silently
        # capping whatever you picked -- so what's shown always matches
        # what you'll actually get.
        is_bar = self.style_combo.currentData() == "bar"
        self.bar_hint_label.setVisible(
            self.sensor_combo.currentData() not in BAR_CAPABLE_SENSORS
            and self.style_combo.currentData() != "history")
        model = self.font_size_combo.model()
        for value, _ in FONT_SIZE_CHOICES:
            item = model.item(value)
            item.setEnabled(not (is_bar and value > MAX_BAR_FONT_SIZE))
        if is_bar and self.font_size_combo.currentData() > MAX_BAR_FONT_SIZE:
            self.font_size_combo.setCurrentIndex(MAX_BAR_FONT_SIZE)
        editable = self.current_screen != "L1"
        self.font_size_combo.setEnabled(editable and self.style_combo.currentData() not in ("history", "gauge"))
        show_orientation = editable and is_bar
        self.orientation_combo.setEnabled(show_orientation)
        self.orientation_label.setVisible(show_orientation)
        self.orientation_combo.setVisible(show_orientation)

    def screen_number(self):
        if self.current_screen == "L1":
            return 1
        return int(self.current_screen[1:])

    def on_add_element(self):
        if self.current_screen == "L1":
            return  # button is disabled for this case, this is just a safety guard
        elements = self.config[self.current_screen]
        sensor_count = sum(1 for el in elements if el.get("kind", "sensor") == "sensor")
        if sensor_count >= MAX_SENSOR_ELEMENTS:
            QMessageBox.warning(self, "Bildschirm voll", f"Jeder Bildschirm unterstützt bis zu {MAX_SENSOR_ELEMENTS} Sensorelemente.")
            return
        # No X/Y fields anymore -- new elements land at a default spot
        # (stacked below whatever's already there) and you drag them
        # into their real place on the preview. y wraps back to the top
        # once it'd run off the bottom of the 43px screen, rather than
        # placing something permanently off-screen.
        #
        # Self-audit bug: this used to stagger by sensor_count alone,
        # so the Nth sensor and the Nth text element (or image) landed
        # on the exact same default spot -- e.g. the first-ever text
        # field and the first-ever sensor both defaulted to (6,6),
        # confirmed by reproducing it directly. Staggering by the
        # TOTAL element count on screen instead means a freshly-added
        # element never lands on top of whatever was added right
        # before it, regardless of kind.
        default_y = (6 + 12 * len(elements)) % LCD_HEIGHT
        orientation = self.orientation_combo.currentData() if self.style_combo.currentData() == "bar" else "horizontal"
        history = self.style_combo.currentData() in ("history", "gauge")
        elements.append({
            "kind": "sensor",
            "sensor": self.sensor_combo.currentData(),
            "style": self.style_combo.currentData(),
            "orientation": orientation,
            "x": 6,
            "y": min(default_y, LCD_HEIGHT - 10) if history else default_y,
            "width": 8 if orientation == "vertical" else 40,
            "height": 10 if history else 28,
            "font_size": self.font_size_combo.currentData(),
        })
        sensor = elements[-1]["sensor"]
        if sensor in DATETIME_FORMAT_DEFAULTS:
            elements[-1]["format"] = DATETIME_FORMAT_DEFAULTS[sensor]
        save_custom_screens(self.config)
        self.refresh_elements_list()
        self.refresh_preview()

    def on_apply_layout_preset(self):
        if self.current_screen == "L1":
            return
        preset = self.layout_preset_combo.currentData()
        answer = QMessageBox.question(
            self,
            "Bildschirmvorlage anwenden",
            f"Alle Elemente auf {load_screens()[self.screen_number()]} durch die Vorlage "
            f"„{PRESET_NAMES[preset]}“ ersetzen?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.config[self.current_screen] = build_layout_preset(preset)
        save_custom_screens(self.config)
        self.refresh_elements_list()
        self.refresh_preview()

    def on_apply_default_layout(self):
        answer = QMessageBox.question(
            self,
            "Standardlayouts",
            "Alle Elemente der vier bearbeitbaren Bildschirme ersetzen?\n\n"
            + "\n".join(f"{SCREEN_NAMES[k]}: {PRESET_NAMES[v]}" for k, v in DEFAULT_SCREEN_PRESETS.items())
            + "\n\nDie bisherigen Bildschirme werden vorher als Sicherung "
              "(custom_screens.txt.vor-standardbelegung) abgelegt.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            if CUSTOM_SCREENS_FILE.exists():
                shutil.copy2(CUSTOM_SCREENS_FILE,
                             CUSTOM_SCREENS_FILE.with_name(CUSTOM_SCREENS_FILE.name + ".vor-standardbelegung"))
        except OSError:
            pass
        for key, preset in DEFAULT_SCREEN_PRESETS.items():
            self.config[key] = build_layout_preset(preset)
        save_custom_screens(self.config)
        self.refresh_elements_list()
        self.refresh_preview()

    def on_apply_profile(self):
        name = self.profile_combo.currentText()
        profile = PROFILES[name]
        ok, err = apply_backlight(profile["rgb"])
        if not ok:
            QMessageBox.warning(self, "Profil", err)
            return
        try:
            show_screen(profile["screen"])
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Profil", f"Bildschirmwechsel fehlgeschlagen: {error}")

    def on_import_image(self):
        if self.current_screen == "L1":
            return  # button is disabled for this case, this is just a safety guard
        elements = self.config[self.current_screen]
        image_count = sum(1 for el in elements if el.get("kind") == "image")
        if image_count >= MAX_IMAGES_PER_SCREEN:
            QMessageBox.warning(
                self, "Bildschirm voll",
                f"Jeder Bildschirm unterstützt bis zu {MAX_IMAGES_PER_SCREEN} Bilder – "
                "der 160x43-Bildschirm ist klein, mehr passt meist ohnehin nicht sinnvoll darauf."
            )
            return

        src_path, _ = QFileDialog.getOpenFileName(
            self, "Bild auswählen", str(Path.home()),
            "Bilder (*.png *.jpg *.jpeg *.bmp *.gif)",
        )
        if not src_path:
            return

        CUSTOM_SCREEN_IMAGES_DIR.mkdir(exist_ok=True)
        # A stable, filesystem-safe name derived from the source file,
        # with a numeric suffix if that name's already taken -- so
        # re-importing the same file twice (or two different files with
        # the same name) doesn't silently clobber an existing one.
        stem = "".join(c if c.isalnum() else "_" for c in Path(src_path).stem) or "image"
        out_path = CUSTOM_SCREEN_IMAGES_DIR / f"{stem}.bin"
        n = 1
        while out_path.exists():
            out_path = CUSTOM_SCREEN_IMAGES_DIR / f"{stem}_{n}.bin"
            n += 1

        # Keep a copy of the real source picture alongside the
        # converted .bin (same disambiguated stem, original extension)
        # -- needed so a later resize can re-convert from real
        # quality instead of upscaling the already-downscaled 1-bit
        # bitmap. Not the same file the user picked: that path could
        # move or be deleted later, this copy is self-contained under
        # DATA_DIR like everything else this app persists.
        src_ext = Path(src_path).suffix or ".png"
        src_copy_path = out_path.with_suffix(src_ext)
        try:
            shutil.copyfile(src_path, src_copy_path)
        except OSError:
            src_copy_path = None  # resize just won't be offered for this image

        # Initial import always goes through png-to-lcd.py's own
        # automatic resize + dithering (already Floyd-Steinberg,
        # confirmed the right algorithm for this) at a sane default
        # size -- 60px is a reasonable default max width for a 160px
        # screen that likely also has sensor elements on it. Dragging
        # the resize handle afterward (see ScreenPreviewCanvas) reruns
        # this exact same converter at a new target size, so quality
        # stays consistent between import and resize.
        max_width = 60
        png_to_lcd = PROJECT_DIR / "src" / "png-to-lcd.py"
        try:
            result = subprocess.run(
                [sys.executable, str(png_to_lcd), src_path, str(out_path), str(max_width), str(LCD_HEIGHT)],
                capture_output=True, text=True, timeout=15,
            )
        except Exception as e:
            QMessageBox.critical(self, "Import fehlgeschlagen", f"Der Konverter konnte nicht gestartet werden: {e}")
            return
        if result.returncode != 0:
            QMessageBox.critical(self, "Import fehlgeschlagen", result.stderr.strip() or "Unbekannter Fehler bei der Bildumwandlung.")
            return
        try:
            w, h = (int(x) for x in result.stdout.split())
        except ValueError:
            QMessageBox.critical(self, "Import fehlgeschlagen", f"Unerwartete Konverter-Ausgabe: {result.stdout!r}")
            return

        # Stagger by the TOTAL element count on screen, not just other
        # images -- same cross-kind collision fix as on_add_element
        # (an image and a same-numbered sensor/text used to be able to
        # land on the same default spot).
        default_x = min(6 + 20 * len(elements), max(0, LCD_WIDTH - w))
        default_y = min(6 + 15 * len(elements), max(0, LCD_HEIGHT - h))
        elements.append({
            "kind": "image",
            "path": f"custom_screen_images/{out_path.name}",  # relative -- matches how the C side resolves it against data_dir()
            "src": f"custom_screen_images/{src_copy_path.name}" if src_copy_path else None,
            "x": default_x, "y": default_y,
            "width": w, "height": h,
        })
        save_custom_screens(self.config)
        self.refresh_elements_list()
        self.refresh_preview()

    def on_add_text(self):
        """Freeform text, not tied to a sensor -- direct request: "L3
        L4 L5 have hard coded text i cant edit move do anything with.
        add an option for me to add text fields too" (referring to the
        "not set up yet" placeholder). Deliberately skips the .meta
        bounds mechanism sensor elements use (that needs real
        font-metric measurement from the C side, keyed to a shared
        index between C's sensor-only array and Python's combined
        list -- extending that correctly for a third element kind
        wasn't worth the risk for a freeform-text feature); hit-testing
        instead uses a simple estimated box, the same category of
        approximation images already accept for their own bounds."""
        if self.current_screen == "L1":
            return  # button is disabled for this case, this is just a safety guard
        elements = self.config[self.current_screen]
        text_count = sum(1 for el in elements if el.get("kind") == "text")
        if text_count >= MAX_TEXTS_PER_SCREEN:
            QMessageBox.warning(
                self, "Bildschirm voll",
                f"Jeder Bildschirm unterstützt bis zu {MAX_TEXTS_PER_SCREEN} Textfelder – "
                "der 160x43-Bildschirm ist klein, mehr passt meist ohnehin nicht sinnvoll darauf."
            )
            return

        content, ok = QInputDialog.getText(self, "Text hinzufügen", "Text, der auf dem Bildschirm angezeigt wird:")
        content = content.strip()
        if not ok or not content:
            return

        # Same staggered-default-position pattern as on_add_element/
        # on_import_image, staggered by the TOTAL element count (see
        # on_add_element for the cross-kind collision this fixes) --
        # otherwise a second text field (or a sensor/image added right
        # after one) could land exactly on top of it.
        default_y = (6 + 12 * len(elements)) % LCD_HEIGHT
        elements.append({
            "kind": "text", "content": content, "x": 6, "y": default_y,
            "font_size": self.font_size_combo.currentData(),
        })
        save_custom_screens(self.config)
        self.refresh_elements_list()
        self.refresh_preview()

    def on_add_visualizer(self):
        """Real-time audio bar visualizer -- direct request: "add ...
        a little visualizer" alongside media info, refined with a
        reference image to a segmented, blocky multi-bar look. Capped
        at 1 per screen (see MAX_VISUALIZERS_PER_SCREEN) since there's
        exactly one persistent audio-capture stream process-wide."""
        if self.current_screen == "L1":
            return  # button is disabled for this case, this is just a safety guard
        elements = self.config[self.current_screen]
        viz_count = sum(1 for el in elements if el.get("kind") == "visualizer")
        if viz_count >= MAX_VISUALIZERS_PER_SCREEN:
            QMessageBox.warning(
                self, "Bildschirm voll",
                f"Jeder Bildschirm unterstützt bis zu {MAX_VISUALIZERS_PER_SCREEN} Visualizer – "
                "es wird nur ein Audiostream gleichzeitig erfasst, ein zweiter würde ihn nur wiederholen."
            )
            return

        default_x = min(6, max(0, LCD_WIDTH - DEFAULT_VISUALIZER_WIDTH))
        default_y = min(3, max(0, LCD_HEIGHT - DEFAULT_VISUALIZER_HEIGHT))
        elements.append({
            "kind": "visualizer", "x": default_x, "y": default_y,
            "width": DEFAULT_VISUALIZER_WIDTH, "height": DEFAULT_VISUALIZER_HEIGHT,
        })
        save_custom_screens(self.config)
        self.refresh_elements_list()
        self.refresh_preview()

    def on_add_frame(self):
        if self.current_screen == "L1":
            return
        elements = self.config[self.current_screen]
        if sum(el.get("kind") == "frame" for el in elements) >= 8:
            QMessageBox.warning(self, "Bildschirm voll", "Jeder Bildschirm unterstützt bis zu 8 Rahmen.")
            return
        elements.insert(0, {"kind": "frame", "x": 2, "y": 2, "width": 40, "height": 20})
        save_custom_screens(self.config)
        self.refresh_elements_list()
        self.refresh_preview()

    def on_remove_element(self, index):
        del self.config[self.current_screen][index]
        save_custom_screens(self.config)
        self.refresh_elements_list()
        self.refresh_preview()

    def on_element_label_edited(self, index, value):
        elements = self.config.get(self.current_screen, [])
        if index < 0 or index >= len(elements):
            return
        el = elements[index]
        if el.get("kind") == "text":
            content = value.strip()[:47]
            if not content:
                return
            el["content"] = content
        elif el.get("kind", "sensor") == "sensor":
            el["label"] = value.strip()[:31]
            el["hide_label"] = not bool(el["label"])
        else:
            return
        save_custom_screens(self.config)
        self.refresh_preview()

    def on_element_format_changed(self, index, sensor, value):
        elements = self.config.get(self.current_screen, [])
        if index < 0 or index >= len(elements):
            return
        el = elements[index]
        valid_formats = {choice for choice, _ in DATETIME_FORMAT_CHOICES.get(sensor, [])}
        if el.get("sensor") != sensor or value not in valid_formats:
            return
        el["format"] = value
        save_custom_screens(self.config)
        self.refresh_preview()

    def on_reset_position(self, index):
        # Direct request: "add a 'reset position' button for elements,
        # in case i lose them off screen too" -- always snaps back to
        # the visible top-left corner (0,0), regardless of element
        # kind or how it ended up off-screen (a hand-edited
        # custom_screens.txt, a stale migrated position, etc.) --
        # simpler and more predictable than trying to guess "where it
        # should go back to".
        el = self.config[self.current_screen][index]
        el["x"], el["y"] = 0, 0
        save_custom_screens(self.config)
        self.refresh_elements_list()
        self.refresh_preview()

    def on_fix_overflow(self):
        # Same size estimate refresh_elements_list uses to decide
        # whether to show this button -- clamps each offending element
        # back so its far edge stays on the visible 160x43 screen,
        # same rule the drag-clamp fix now enforces for new drags.
        for el in self.config[self.current_screen]:
            if el.get("kind") in ("image", "visualizer", "frame") or el.get("style") in ("history", "gauge"):
                w, h = el.get("width", 0), el.get("height", 0)
            elif el.get("kind") == "text":
                _, h_ratio = FONT_SIZE_SCALE.get(el.get("font_size", 0), (1.0, 1.0))
                w, h = TEXT_CHAR_PX, round(ELEMENT_HIT_H * h_ratio)
            elif el.get("style") == "bar" and el.get("orientation") == "vertical":
                w, h = el.get("width", 8), el.get("height", 28)
            else:
                w, h = el.get("max_width", 0) or ELEMENT_HIT_W, ELEMENT_HIT_H
            el["x"] = max(0, min(el["x"], LCD_WIDTH - w))
            el["y"] = max(0, min(el["y"], LCD_HEIGHT - h))
        save_custom_screens(self.config)
        self.refresh_elements_list()
        self.refresh_preview()

    def on_cycle_font_size(self, index):
        el = self.config[self.current_screen][index]
        # Bars cap at Medium -- same reasoning as on_style_changed's
        # greyed-out Large/Huge options, applied here too so an
        # existing bar element can't cycle past it either.
        is_bar = el.get("kind") == "sensor" and el.get("style") == "bar"
        max_size = MAX_BAR_FONT_SIZE if is_bar else len(FONT_SIZE_CHOICES) - 1
        el["font_size"] = (el.get("font_size", 0) + 1) % (max_size + 1)
        save_custom_screens(self.config)
        self.refresh_elements_list()
        self.refresh_preview()

    def on_element_dragged(self, index, x, y):
        elements = self.preview_canvas._elements
        if 0 <= index < len(elements) and elements[index].get("kind") == "game_dashboard":
            element = elements[index]
            component = element["component"]
            self.game_dashboard_offsets[component]["x"] = x - element["base_x"]
            self.game_dashboard_offsets[component]["y"] = y - element["base_y"]
            save_game_dashboard_offsets(self.game_dashboard_offsets)
            return
        # Called continuously while dragging. Saving here (a cheap text
        # write, not the render itself) is what actually makes the live
        # preview live -- render_preview() runs the real C binary,
        # which reads custom_screens.txt fresh from disk every time.
        # Without saving mid-drag, the drag_refresh_timer's periodic
        # refresh_preview() calls kept re-rendering the OLD saved
        # position the whole time you were dragging -- only the dashed
        # selection outline moved with the mouse, the actual rendered
        # bar/label stayed frozen until release. Real bug, reported
        # directly as the preview being "hard to control."
        save_custom_screens(self.config)
        self.refresh_elements_list()

    def on_element_resized(self, index, width):
        # Same idea and same fix as on_element_dragged.
        save_custom_screens(self.config)
        self.refresh_elements_list()

    def on_image_resize_requested(self, index, target_w, target_h):
        # Deliberately NOT the same pattern as on_element_resized: a bar
        # resize is just a number, cheap to save on every mouse-move
        # event. An image resize has to re-run png-to-lcd.py and rewrite
        # the .bin file on disk -- self-audit measured that at ~85-90ms
        # per call, so it runs on a background ImageResizeWorker instead
        # of blocking the GUI thread. If one's already running, the
        # latest target is coalesced into _image_resize_next rather than
        # piling up overlapping subprocesses; _start_image_resize_worker
        # picks that up the moment the current one finishes.
        if self._image_resize_worker is not None and self._image_resize_worker.isRunning():
            self._image_resize_next = (index, target_w, target_h)
            return
        self._start_image_resize_worker(index, target_w, target_h)

    def _start_image_resize_worker(self, index, target_w, target_h):
        elements = self.config.get(self.current_screen, [])
        if index >= len(elements):
            return
        el = elements[index]
        if el.get("kind") != "image" or not el.get("src"):
            return
        src_full = DATA_DIR / el["src"]
        out_full = DATA_DIR / el["path"]
        png_to_lcd = PROJECT_DIR / "src" / "png-to-lcd.py"
        self._image_resize_screen = self.current_screen
        # Real bug found by self-audit: an index alone isn't a stable
        # identity across an async gap. Removing (or reordering) an
        # earlier element while this worker is still running would
        # leave a DIFFERENT element sitting at `index` by the time the
        # result comes back -- confirmed with a real "remove element 0
        # while resizing element 0" race, which misapplied the resize
        # to the surviving element that shifted into that slot. `el`
        # itself is the same dict object Python already holds a
        # reference to in the list -- keeping that reference lets
        # _on_image_resize_finished verify identity (`is`), not just
        # a bounds check, before writing anything.
        self._image_resize_el = el
        worker = ImageResizeWorker(index, src_full, out_full, target_w, target_h, png_to_lcd)
        worker.finished_resize.connect(self._on_image_resize_finished)
        self._image_resize_worker = worker
        worker.start()

    def _on_image_resize_finished(self, index, w, h, ok):
        started_on = self._image_resize_screen
        el_token = self._image_resize_el
        self._image_resize_worker = None
        self._image_resize_el = None
        if ok and started_on == self.current_screen:
            elements = self.config.get(self.current_screen, [])
            if index < len(elements) and elements[index] is el_token:
                elements[index]["width"], elements[index]["height"] = w, h
                save_custom_screens(self.config)
                self.refresh_preview()
        if self._image_resize_next is not None:
            next_index, next_w, next_h = self._image_resize_next
            self._image_resize_next = None
            self._start_image_resize_worker(next_index, next_w, next_h)

    def on_drag_started(self):
        # Pause the 1s idle timer while the 120ms drag timer takes
        # over -- both ultimately call the same refresh_preview(),
        # writing to the same file; no reason to run both at once.
        self.preview_timer.stop()
        self.drag_refresh_timer.start(120)

    def on_drag_finished(self):
        self.drag_refresh_timer.stop()
        save_custom_screens(self.config)
        self.refresh_preview()  # one final, accurate, untimed refresh
        self.preview_timer.start(1000)

    def refresh_elements_list(self):
        # Clear everything including the trailing stretch, then rebuild
        # it fresh each time -- simplest way to keep the stretch at the
        # end regardless of how many rows there are now.
        while self.elements_layout.count():
            item = self.elements_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._element_rows = []
        self.on_preview_element_hovered(-1)

        if self.current_screen == "L1" or self._design_index != 0:
            self.fix_overflow_btn.hide()
            info = QLabel("Fertige Designs sind nicht frei verschiebbar. Oben auswählen "
                          "oder mit L2/L3 blättern. Design 1 erhält deine eigenen Elemente.")
            info.setWordWrap(True)
            info.setObjectName("Status")
            self.elements_layout.addWidget(info)
            self.elements_layout.addStretch()
            return

        elements = self.config[self.current_screen]
        # Recovery-button visibility: rough estimate (not pixel-perfect
        # -- this is just "does it look like something's clipped",
        # matching the same category of approximation already used
        # elsewhere for kinds without exact measured bounds) of whether
        # any element's content likely extends past the visible screen.
        overflowing = False
        for el in elements:
            if el.get("kind") in ("image", "visualizer", "frame") or el.get("style") in ("history", "gauge"):
                w, h = el.get("width", 0), el.get("height", 0)
            elif el.get("kind") == "text":
                _, h_ratio = FONT_SIZE_SCALE.get(el.get("font_size", 0), (1.0, 1.0))
                w, h = TEXT_CHAR_PX, round(ELEMENT_HIT_H * h_ratio)
            elif el.get("style") == "bar" and el.get("orientation") == "vertical":
                w, h = el.get("width", 8), el.get("height", 28)
            else:
                w, h = el.get("max_width", 0) or ELEMENT_HIT_W, ELEMENT_HIT_H
            if el["x"] + w > LCD_WIDTH or el["y"] + h > LCD_HEIGHT:
                overflowing = True
                break
        self.fix_overflow_btn.setVisible(overflowing)

        if not elements:
            self.elements_layout.addWidget(QLabel("Auf diesem Bildschirm ist noch nichts."))
            self.elements_layout.addStretch()
            return
        for i, el in enumerate(elements):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            kind = el.get("kind", "sensor")
            has_size_btn = (kind in ("sensor", "text")
                            and el.get("style") not in ("history", "gauge")
                            and not (el.get("hide_label") and el.get("style") == "bar"))
            # Position/width shown on the canvas itself now (drag to
            # move, drag the handle to resize) -- repeating exact
            # coordinates here just made rows overflow the narrow panel
            # and need a horizontal scrollbar, so this stays short.
            if kind == "frame":
                text = QLabel(f"Rahmen {el['width']}x{el['height']}")
                text.setToolTip(
                    f"x={el['x']} y={el['y']}\nAm Rand verschieben, an der Ecke skalieren.")
            elif kind == "image":
                name = Path(el["path"]).stem
                text = QLabel(f"Bild: {name}")
                text.setToolTip(f"x={el['x']} y={el['y']} {el['width']}x{el['height']}px")
            elif kind == "text":
                text = QLineEdit(el["content"])
                text.setPlaceholderText("LCD-Text")
                text.setAccessibleName("Auf dem LCD angezeigter Text")
                text.setToolTip("Den auf dem LCD angezeigten Text bearbeiten, dann Enter drücken.")
                text.editingFinished.connect(
                    lambda idx=i, editor=text: self.on_element_label_edited(idx, editor.text())
                )
            elif kind == "visualizer":
                text = QLabel("Visualizer (Live-Audio)")
                text.setToolTip(f"x={el['x']} y={el['y']} {el['width']}x{el['height']}px")
            elif el.get("style") == "history":
                text = QLabel("DL-Verlauf" if el["sensor"] == "NET_DOWN" else "UL-Verlauf")
                text.setToolTip(
                    "Letzte 60 Messwerte, eigene automatische Höhenskala. "
                    f"x={el['x']} y={el['y']} {el['width']}x{el['height']}px\n"
                    "In der Vorschau ziehen oder an der Ecke skalieren.")
            elif el.get("style") == "gauge":
                text = QLabel(SENSOR_LABELS.get(el["sensor"], el["sensor"]))
                text.setToolTip(
                    "Füllbalken mit integriertem Wert, ohne separate Beschriftung.\n"
                    f"x={el['x']} y={el['y']} {el['width']}x{el['height']}px\n"
                    "In der Vorschau ziehen oder an der Ecke skalieren.")
            else:
                sensor = el["sensor"]
                sensor_name = SENSOR_LABELS.get(sensor, sensor)
                if sensor in DATETIME_FORMAT_CHOICES:
                    text = QComboBox()
                    text.setAccessibleName(f"{sensor_name} – Format")
                    text.setToolTip(f"Format für „{sensor_name}“ wählen; LCD-Beschriftungen werden hier nicht verwendet.")
                    compact_formats = {
                        "TIME": {
                            "hms": "24h+S",
                            "hm": "24h",
                            "ampm": "12h",
                        },
                        "DATE": {
                            "short": "TTMon",
                            "eu": "EU 4J",
                            "eu_short": "EU",
                            "iso": "ISO",
                        },
                    }
                    for value, label in DATETIME_FORMAT_CHOICES[sensor]:
                        text.addItem(compact_formats[sensor][value], value)
                        text.setItemData(text.count() - 1, label, Qt.ToolTipRole)
                    current_format = el.get("format") or DATETIME_FORMAT_DEFAULTS[sensor]
                    format_index = text.findData(current_format)
                    if format_index >= 0:
                        text.setCurrentIndex(format_index)
                    text.currentIndexChanged.connect(
                        lambda _, idx=i, selected_sensor=sensor, combo=text:
                        self.on_element_format_changed(idx, selected_sensor, combo.currentData())
                    )
                else:
                    label = "" if el.get("hide_label") else (
                        el.get("label") or DEFAULT_SENSOR_DISPLAY_LABELS.get(sensor, sensor_name))
                    text = QLineEdit(label)
                    text.setPlaceholderText(sensor_name if el.get("hide_label") else "LCD-Beschriftung")
                    text.setAccessibleName(f"LCD-Beschriftung für {sensor}")
                    orientation = (
                        f", {el['orientation']}"
                        if el.get("style") == "bar" and el.get("orientation") == "vertical"
                        else ""
                    )
                    text.setToolTip(
                        f"LCD-Beschriftung bearbeiten; zum Speichern Enter drücken.\nSensor: {sensor_name}"
                        f"\nAnzeige: {el['style']}{orientation}"
                        f"\nx={el['x']} y={el['y']}"
                        + (f" Breite={el.get('width', 40)}" if el.get("style") == "bar" else "")
                    )
                    text.editingFinished.connect(
                        lambda idx=i, editor=text: self.on_element_label_edited(idx, editor.text())
                    )
            text.setStyleSheet("font-size: 11px; padding: 2px;")
            text.setFixedSize(ELEMENT_ROW_FIELD_WIDTH, 30)
            # Keep the primary cell fixed-width; static names are
            # elided to its usable width and preserved in the tooltip.
            if isinstance(text, QLabel):
                full_text = text.text()
                text.setText(
                    QFontMetrics(text.font()).elidedText(
                        full_text, Qt.ElideRight, ELEMENT_ROW_FIELD_WIDTH - 8
                    )
                )
                if text.toolTip():
                    text.setToolTip(full_text + "\n" + text.toolTip())
                else:
                    text.setToolTip(full_text)
            row.addWidget(text)
            row.addStretch()
            if has_size_btn:
                # Direct request: "id like to be able to resize
                # elements". No drag handle here on purpose -- the
                # library only has 4 discrete text sizes (no continuous
                # scaling), so cycling through them with a click is the
                # honest equivalent of resizing for these element kinds.
                size_label = FONT_SIZE_CHOICES[el.get("font_size", 0)][1]
                size_btn = QPushButton(size_label)
                size_btn.setFixedSize(56, 30)
                size_btn.setStyleSheet("padding: 1px; font-size: 10px;")
                size_btn.setToolTip("Klicken, um die Textgröße zu wechseln: Klein -> Mittel -> Groß -> Riesig")
                size_btn.clicked.connect(lambda _, idx=i: self.on_cycle_font_size(idx))
                row.addWidget(size_btn)
            else:
                size_spacer = QWidget()
                size_spacer.setFixedSize(56, 30)
                row.addWidget(size_spacer)
            # Direct request: "add a 'reset position' button for
            # elements, in case i lose them off screen too" -- snaps
            # x/y back to the visible top-left corner regardless of
            # element kind, so a dragged-off-screen element is always
            # recoverable without having to guess at coordinates.
            reset_btn = QPushButton("⌂")
            reset_btn.setFixedSize(28, 30)
            reset_btn.setStyleSheet("padding: 1px;")
            reset_btn.setToolTip("Position auf oben links zurücksetzen (falls du das Element aus dem Bild gezogen hast)")
            reset_btn.clicked.connect(lambda _, idx=i: self.on_reset_position(idx))
            row.addWidget(reset_btn)
            remove_btn = QPushButton("✕")
            remove_btn.setFixedSize(28, 30)
            remove_btn.setStyleSheet("padding: 1px;")
            remove_btn.setToolTip("Dieses Element vom Bildschirm entfernen")
            remove_btn.clicked.connect(lambda _, idx=i: self.on_remove_element(idx))
            row.addWidget(remove_btn)
            container = QWidget()
            container.setLayout(row)
            container.setObjectName("ElementRow")
            container.setStyleSheet(
                "QWidget#ElementRow { background-color: transparent; "
                "border: 1px solid transparent; border-radius: 3px; }"
            )
            container.setFixedHeight(34)
            self.elements_layout.addWidget(container)
            self._element_rows.append(container)
        self.elements_layout.addStretch()
        hovered_index = self.preview_canvas._hover_index
        if hovered_index is not None:
            self.on_preview_element_hovered(hovered_index)

    def on_preview_element_hovered(self, index):
        elements = self.preview_canvas._elements
        if index >= 0 and index < len(elements) and elements[index].get("kind") == "game_dashboard":
            index = -1
        for row_index, row in enumerate(self._element_rows):
            hovered = row_index == index
            row.setStyleSheet(
                "QWidget#ElementRow { background-color: %s; border: 1px solid %s; "
                "border-radius: 3px; }" % (
                    "#26364a" if hovered else "transparent",
                    "#ffbe28" if hovered else "transparent",
                )
            )

    def on_clock_layout_selected(self):
        try:
            save_clock_layout(self.clock_layout_combo.currentData())
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Uhr-Design", f"Speichern fehlgeschlagen: {error}")
        self.refresh_preview()

    def cycle_clock_layout(self, step):
        try:
            save_clock_layout((load_clock_layout() + step) % len(CLOCK_LAYOUTS))
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Uhr-Design", str(error))
        self.refresh_preview()

    def populate_design_choices(self):
        names = SCREEN_DESIGNS.get(self.screen_number(), ())
        self.design_row.setVisible(bool(names))
        self.design_combo.clear()
        for index, name in enumerate(names):
            self.design_combo.addItem(f"{index + 1:02d} / {len(names)} · {name}", index)

    def on_screen_design_selected(self):
        try:
            save_screen_design(self.screen_number(), self.design_combo.currentData())
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Screen-Design", f"Speichern fehlgeschlagen: {error}")
        self.refresh_preview()

    def cycle_screen_design(self, step):
        try:
            screen = self.screen_number()
            save_screen_design(screen, (load_screen_design(screen) + step) % len(SCREEN_DESIGNS[screen]))
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Screen-Design", str(error))
        self.refresh_preview()

    def refresh_preview(self):
        design = 0
        if self.screen_number() in SCREEN_DESIGNS:
            try:
                design = load_screen_design(self.screen_number())
            except (OSError, ValueError) as error:
                self._design_index = -1
                self.editor_panel.setEnabled(False)
                self.drag_hint.setText(f"Screen-Design konnte nicht geladen werden: {error}")
                self.refresh_elements_list()
                self.preview_canvas.set_data(None, [])
                return
            self.design_combo.setCurrentIndex(design)
        self.editor_panel.setEnabled(design == 0 and self.current_screen != "L1")
        if self._design_index != design:
            self._design_index = design
            self.refresh_elements_list()
            if design == 0 and self.screen_number() in SCREEN_DESIGNS:
                self.drag_hint.setText(
                    "Design 1: Dein bisheriges Layout bleibt frei bearbeitbar. "
                    "L2/L3 oder die Auswahl oben wechseln zu den fertigen Designs.")
        if design:
            self.drag_hint.setText(
                "20 Screen-Designs: L2 zurück / L3 weiter (Standardbelegung). "
                "Fertige Designs sind schreibgeschützt. Design 1 erhält dein bearbeitbares Layout.")
            if self.current_screen == "L4":
                self.drag_hint.setText(
                    "20 Warteanimationen: L2 zurück / L3 weiter. Ohne laufendes Spiel "
                    "wird die gewählte Animation gezeigt; im Spiel weiterhin Logo/Titel.")
            elif self.current_screen == "L3":
                self.drag_hint.setText(
                    "20 Warteanimationen: L2 zurück / L3 weiter. Ohne Medien wird die "
                    "gewählte Animation gezeigt; bei Wiedergabe oder Pause weiterhin Titel und Player.")
        if hasattr(self, "preview_timer"):
            interval = 250 if self.current_screen in ("L3", "L4") and design > 0 else 1000
            if self.preview_timer.interval() != interval:
                self.preview_timer.setInterval(interval)
        if self.current_screen == "L1":
            try:
                index = load_clock_layout()
            except (OSError, ValueError) as error:
                self.drag_hint.setText(f"Uhr-Design konnte nicht geladen werden: {error}")
                self.preview_canvas.set_data(None, [])
                return
            self.clock_layout_combo.setCurrentIndex(index)
            self.drag_hint.setText(
                "20 Uhr-Designs: Auswahl oben oder auf der Tastatur mit L2 zurück / L3 weiter "
                "(Standardbelegung). Die Auswahl bleibt gespeichert.")
        # Image resize regen now happens on a background worker (see
        # ImageResizeWorker/_on_image_resize_finished) which calls this
        # itself once the .bin file + el["width"/"height"] are updated
        # together -- nothing to apply synchronously here anymore.
        pixmap, bounds, err = render_preview(self.screen_number(), tag="editor", editor=True)
        if pixmap is None:
            print(f"Fehler bei der Vorschau der eigenen Bildschirme: {err}")  # surfaced in the panel below instead of blocking the canvas
            return
        scaled = pixmap.scaled(
            LCD_WIDTH * PREVIEW_SCALE, LCD_HEIGHT * PREVIEW_SCALE,
            Qt.KeepAspectRatio, Qt.FastTransformation,
        )
        elements = [] if design else self.config.get(self.current_screen, [])
        game_bounds = {
            component: bounds.get(GAME_BOUNDS_BASE + index)
            for index, component in enumerate(GAME_DASHBOARD_COMPONENTS)
        }
        if self.current_screen == "L4" and not design and game_bounds["cpu"] and game_bounds["gpu"]:
            elements = []
            for component, bound_index in zip(GAME_DASHBOARD_COMPONENTS, range(GAME_BOUNDS_BASE, GAME_BOUNDS_BASE + 3)):
                bound = bounds.get(bound_index)
                if not bound:
                    continue
                element = self._game_dashboard_elements.setdefault(
                    component,
                    {"kind": "game_dashboard", "component": component, "bounds_index": bound_index},
                )
                element.update({
                    "x": bound.get("anchor_x", bound["label_x1"]),
                    "y": bound.get("anchor_y", bound["label_y1"]),
                    "base_x": bound.get("base_x", bound.get("anchor_x", bound["label_x1"])),
                    "base_y": bound.get("base_y", bound.get("anchor_y", bound["label_y1"])),
                })
                elements.append(element)
            self.drag_hint.setText(
                "Spieldashboard aktiv: Logo/Titel oder CPU-/GPU-Block ziehen, um es zu positionieren."
            )
        elif self.current_screen == "L4" and not design:
            self.drag_hint.setText(
                "L4-Layoutelemente hier ziehen. Während ein Spiel läuft, wird stattdessen das "
                "automatische Spieldashboard angezeigt."
            )
        self.preview_canvas.set_data(scaled, elements, bounds)


class GameLogosTab(QWidget):
    """Lists the installed Steam games and lets you replace each game's
    LCD logo with your own image (stored as
    ~/.local/share/g510-lcd/custom_logos/<appid>.png)."""

    HIDDEN_WORDS = ("proton", "steam linux runtime", "steamworks", "redistrib")

    def __init__(self):
        super().__init__()
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "pregenerate_game_logos",
            PROJECT_DIR / "scripts" / "pregenerate-game-logos.py")
        self.steam = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.steam)
        self.logo_dir = DATA_DIR / "game_logos"
        self.custom_dir = DATA_DIR / "custom_logos"
        self.games = {}
        self.logo_generator = QProcess(self)
        self.logo_generator.finished.connect(self.on_logos_generated)
        self.logo_generator.errorOccurred.connect(self.on_logo_generation_error)

        layout = QHBoxLayout(self)
        left = QVBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Installierte Spiele durchsuchen...")
        self.search.textChanged.connect(self.fill_list)
        self.show_tools = QCheckBox("Proton / Laufzeitumgebungen anzeigen")
        self.show_tools.toggled.connect(self.fill_list)
        self.list = QListWidget()
        self.list.setMinimumWidth(320)
        self.list.currentItemChanged.connect(self.update_detail)
        left.addWidget(self.search)
        left.addWidget(self.list)
        left.addWidget(self.show_tools)
        layout.addLayout(left, 1)

        right = QVBoxLayout()
        self.title_label = QLabel("Spiel auswählen")
        self.title_label.setWordWrap(True)
        self.preview = QLabel()
        self.preview.setFixedSize(160 * 4 + 8, 43 * 4 + 8)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("background:#c0d796;border:1px solid #555;")
        self.source_label = QLabel("")
        self.game_color_label = QLabel()
        self.game_color_label.setWordWrap(True)
        self.game_color_button = QPushButton("Tastaturfarbe für dieses Spiel wählen...")
        self.game_color_button.clicked.connect(self.choose_game_color)
        self.clear_game_color_button = QPushButton("Keine eigene Spielfarbe")
        self.clear_game_color_button.clicked.connect(self.clear_game_color)
        color_note = QLabel(
            "Das Spiel im Vordergrund bestimmt die Farbe. Ohne Spielfokus bleibt "
            "die bisherige Spielfarbe, solange dieses Spiel läuft. Nach Spielende "
            "kehrt die gespeicherte Standardfarbe zurück. Funktioniert auch ohne "
            "geöffnetes Tool (KDE/KWin oder X11).")
        color_note.setWordWrap(True)
        self.optimize_logo = QCheckBox("Für LCD optimieren (160×43, Schwarz-Weiß)")
        self.optimize_logo.setToolTip(
            "Entfernt leere Ränder und passt Kontrast und Schwarz-Weiß-Schwelle an. "
            "Ausschalten: bisherige Darstellung aus dem unveränderten Original.")
        self.optimize_logo.toggled.connect(self.on_logo_optimization_changed)
        self.choose_btn = QPushButton("Eigenes Logo wählen...")
        self.choose_btn.clicked.connect(self.choose_logo)
        self.reset_btn = QPushButton("Zurück zum automatischen Logo")
        self.reset_btn.clicked.connect(self.reset_logo)
        hint = QLabel(
            "Wähle ein klares, kontrastreiches Bild (Weiß auf Dunkel wird automatisch "
            "invertiert). Neue Importe werden für das LCD optimiert: leere Ränder "
            "entfernen, proportional einpassen und Schwarz-Weiß-Kontrast anpassen. "
            "Der Schalter stellt die bisherige Darstellung wieder her; das Original "
            "bleibt erhalten. Die Vorschau aktualisiert sich direkt nach dem Import. "
            "Das LCD verwendet es beim nächsten Start des Spiels.")
        hint.setWordWrap(True)
        for w in (self.title_label, self.preview, self.source_label,
                  self.optimize_logo, self.choose_btn, self.reset_btn, hint,
                  self.game_color_label, self.game_color_button,
                  self.clear_game_color_button, color_note):
            right.addWidget(w)
        right.addStretch(1)
        layout.addLayout(right, 2)
        self.choose_btn.setEnabled(False)
        self.reset_btn.setEnabled(False)
        self.optimize_logo.setEnabled(False)
        self.refresh_game_color()

    def showEvent(self, event):
        super().showEvent(event)
        libs = self.steam.libraries()
        self.libs = libs
        self.games = self.steam.games(libs)
        self.fill_list()
        # Creates the automatic logos that don't exist yet; skips the rest.
        if self.logo_generator.state() == QProcess.NotRunning:
            self.logo_generator.start(
                sys.executable, [str(PROJECT_DIR / "scripts" / "pregenerate-game-logos.py")])

    def on_logos_generated(self, exit_code, exit_status):
        error = bytes(self.logo_generator.readAllStandardError()).decode(errors="replace").strip()
        self.logo_generator.readAllStandardOutput()
        self.update_detail()
        if exit_status != QProcess.NormalExit or exit_code != 0:
            self.source_label.setText(
                f"Automatische Logo-Erzeugung fehlgeschlagen: {error or f'Exit-Code {exit_code}'}")

    def on_logo_generation_error(self, error):
        if error == QProcess.FailedToStart:
            self.source_label.setText(
                f"Automatische Logo-Erzeugung konnte nicht gestartet werden: "
                f"{self.logo_generator.errorString()}")

    def fill_list(self, *_, selected_appid=None):
        needle = self.search.text().strip().lower()
        current = self.current_appid() if selected_appid is None else selected_appid
        self.list.blockSignals(True)
        self.list.clear()
        for appid, name in sorted(self.games.items(), key=lambda g: g[1].lower()):
            lowered = name.lower()
            if not self.show_tools.isChecked() and any(w in lowered for w in self.HIDDEN_WORDS):
                continue
            if needle and needle not in lowered and needle not in str(appid):
                continue
            has_custom = (self.custom_dir / f"{appid}.png").is_file()
            item = QListWidgetItem(f"{name}  [{appid}]" + ("  *" if has_custom else ""))
            item.setData(Qt.UserRole, appid)
            self.list.addItem(item)
            if appid == current:
                self.list.setCurrentItem(item)
        self.list.blockSignals(False)
        self.update_detail()

    def current_appid(self):
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def render_bin(self, appid):
        size_file = self.logo_dir / f"{appid}.size"
        bin_file = self.logo_dir / f"{appid}.bin"
        try:
            w, h = map(int, size_file.read_text().split())
            data = bin_file.read_bytes()
        except (OSError, ValueError):
            return None
        if not (0 < w <= LCD_WIDTH and 0 < h <= LCD_HEIGHT):
            return None
        row = (w + 7) // 8
        if len(data) < row * h:
            return None
        img = QImage(160, 43, QImage.Format_RGB32)
        img.fill(QColor("#c0d796"))
        ox, oy = (160 - w) // 2, (43 - h) // 2
        dark = QColor("#1b2a14").rgb()
        for y in range(h):
            for x in range(w):
                if (data[y * row + x // 8] >> (x % 8)) & 1:
                    img.setPixel(ox + x, oy + y, dark)
        return img.scaled(160 * 4, 43 * 4, Qt.KeepAspectRatio, Qt.FastTransformation)

    def update_detail(self, *_):
        appid = self.current_appid()
        self.refresh_game_color()
        self.choose_btn.setEnabled(appid is not None)
        has_custom = appid is not None and (self.custom_dir / f"{appid}.png").is_file()
        self.optimize_logo.setEnabled(has_custom)
        self.optimize_logo.blockSignals(True)
        self.optimize_logo.setChecked(
            has_custom and (self.custom_dir / f"{appid}.optimized").is_file())
        self.optimize_logo.blockSignals(False)
        if appid is None:
            self.title_label.setText("Spiel auswählen")
            self.preview.clear()
            self.source_label.setText("")
            self.reset_btn.setEnabled(False)
            return
        self.title_label.setText(f"{self.games.get(appid, '?')}  (App ID {appid})")
        has_custom = (self.custom_dir / f"{appid}.png").is_file()
        shipped = (PROJECT_DIR / "assets" / "logos" / f"{appid}.png").is_file()
        self.reset_btn.setEnabled(has_custom)
        self.source_label.setText(
            ("Quelle: dein eigenes Logo · LCD-optimiert" if self.optimize_logo.isChecked()
             else "Quelle: dein eigenes Logo · Original-Darstellung") if has_custom else
            "Quelle: im Projekt enthaltenes Logo" if shipped else
            "Quelle: automatisch (Steam-Artwork)")
        pix = self.render_bin(appid)
        if pix is None:
            self.preview.setText("Noch kein Logo erzeugt – in einem Moment erneut auswählen")
        else:
            self.preview.setPixmap(QPixmap.fromImage(pix))

    def refresh_game_color(self):
        appid = self.current_appid()
        self.game_color_button.setEnabled(appid is not None)
        self.clear_game_color_button.setEnabled(False)
        try:
            color = game_colors.load_colors().get(str(appid))
        except (OSError, ValueError) as error:
            self.game_color_label.setText(f"Spielfarbe konnte nicht geladen werden: {error}")
            return
        self.clear_game_color_button.setEnabled(color is not None)
        self.game_color_label.setText(
            "Tastaturfarbe: " + QColor(*color).name().upper() if color else
            "Tastaturfarbe: keine eigene Farbe")
        self.game_color_label.setStyleSheet(
            f"border-left: 12px solid {QColor(*color).name()}; padding-left: 8px;"
            if color else "")

    def choose_game_color(self):
        appid = self.current_appid()
        if appid is None:
            return
        try:
            current = game_colors.load_colors().get(str(appid))
            color = QColorDialog.getColor(
                QColor(*current) if current else QColor("#ffffff"), self,
                f"Tastaturfarbe: {self.games[appid]}")
            if not color.isValid():
                return
            game_colors.save_color(appid, (color.red(), color.green(), color.blue()))
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Spielfarbe", f"Speichern fehlgeschlagen: {error}")
        self.refresh_game_color()

    def clear_game_color(self):
        appid = self.current_appid()
        if appid is None:
            return
        try:
            game_colors.save_color(appid, None)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Spielfarbe", f"Entfernen fehlgeschlagen: {error}")
        self.refresh_game_color()

    def convert(self, appid, custom, optimized=None):
        """Regenerates the cached .bin/.size exactly like the service does."""
        import tempfile
        self.logo_dir.mkdir(parents=True, exist_ok=True)
        converter = str(PROJECT_DIR / "src" / "png-to-lcd.py")
        if custom:
            source = custom
            flags = ["--upscale", "--invert-dark"]
            if optimized is None:
                optimized = (self.custom_dir / f"{appid}.optimized").is_file()
            if optimized:
                flags.append("--lcd-logo")
        else:
            shipped = PROJECT_DIR / "assets" / "logos" / f"{appid}.png"
            source = shipped if shipped.is_file() else self.steam.find_artwork(self.libs, appid)
            flags = ["--upscale"]
            if not shipped.is_file():
                flags += ["--trim-transparent", "--invert-dark", "--boost-wide", "--best-logo"]
        with tempfile.TemporaryDirectory(prefix=".logo-", dir=self.logo_dir) as temporary:
            output = Path(temporary) / f"{appid}.bin"
            cmd = ([sys.executable, converter, str(source), str(output), "160", "43", *flags]
                   if source else
                   [sys.executable, str(PROJECT_DIR / "src" / "title-to-lcd.py"),
                    self.games[appid], str(output)])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                raise ValueError(result.stderr.strip() or
                                 f"Logo-Umwandlung fehlgeschlagen (Exit-Code {result.returncode}).")
            try:
                width, height = map(int, result.stdout.split())
            except ValueError as error:
                raise ValueError("Die Logo-Umwandlung lieferte keine gültige Bildgröße.") from error
            if not (0 < width <= LCD_WIDTH and 0 < height <= LCD_HEIGHT):
                raise ValueError("Das erzeugte Logo passt nicht auf das 160x43-Display.")
            if output.stat().st_size != ((width + 7) // 8) * height:
                raise ValueError("Die erzeugten Logo-Bilddaten sind unvollständig.")
            size = Path(temporary) / f"{appid}.size"
            size.write_text(f"{width} {height}\n")
            output.replace(self.logo_dir / output.name)
            size.replace(self.logo_dir / size.name)

    def choose_logo(self):
        appid = self.current_appid()
        if appid is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Logo-Bild auswählen", str(Path.home()),
            "Bilder (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        if not path:
            return
        import tempfile
        try:
            image = QImage(path)
            if image.isNull():
                raise ValueError("Die gewählte Datei konnte nicht als Bild gelesen werden.")
            self.custom_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".import-", dir=self.custom_dir) as temporary:
                target = Path(temporary) / f"{appid}.png"
                if not image.save(str(target), "PNG"):
                    raise OSError("Das Bild konnte nicht im PNG-Format gespeichert werden.")
                marker = Path(temporary) / f"{appid}.optimized"
                marker.write_text("1\n")
                self.convert(appid, target, optimized=True)
                target.replace(self.custom_dir / target.name)
                marker.replace(self.custom_dir / marker.name)
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            QMessageBox.warning(self, "Logo-Import fehlgeschlagen", str(exc))
            return
        self.fill_list(selected_appid=appid)
        self.source_label.setText("Quelle: dein eigenes Logo · LCD-optimiert · Import erfolgreich")

    def on_logo_optimization_changed(self, enabled):
        appid = self.current_appid()
        if appid is None:
            return
        try:
            self.convert(appid, self.custom_dir / f"{appid}.png", optimized=enabled)
            marker = self.custom_dir / f"{appid}.optimized"
            if enabled:
                marker.write_text("1\n")
            else:
                marker.unlink(missing_ok=True)
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            QMessageBox.warning(self, "Logo-Optimierung fehlgeschlagen", str(exc))
        self.update_detail()

    def reset_logo(self):
        appid = self.current_appid()
        if appid is None:
            return
        try:
            self.convert(appid, None)
            (self.custom_dir / f"{appid}.png").unlink(missing_ok=True)
            (self.custom_dir / f"{appid}.optimized").unlink(missing_ok=True)
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            QMessageBox.warning(self, "Logo zurücksetzen fehlgeschlagen", str(exc))
            return
        self.fill_list(selected_appid=appid)


class OverviewTab(QWidget):
    navigate = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        cards = QHBoxLayout()
        self.screen_name = QLabel()
        self.screen_count = QLabel()
        for title, value in (("Aktiver LCD-Bildschirm", self.screen_name),
                             ("Verfügbare Bildschirme", self.screen_count)):
            card = QWidget()
            card.setObjectName("Card")
            box = QVBoxLayout(card)
            box.setContentsMargins(20, 16, 20, 16)
            box.addWidget(QLabel(title))
            value.setObjectName("Metric")
            value.setWordWrap(True)
            value.setTextFormat(Qt.PlainText)
            box.addWidget(value)
            cards.addWidget(card, 1)
        layout.addLayout(cards)
        layout.addWidget(QLabel("Live-Vorschau · Logitech G510s · 160 × 43 Pixel"))
        self.preview = ScreenPreviewCanvas()
        self.preview.setEnabled(False)
        layout.addWidget(self.preview, 1)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setTextFormat(Qt.PlainText)
        layout.addWidget(self.error)
        actions = QHBoxLayout()
        for name, index in (("LCD-Bildschirme gestalten", 1), ("LCD-Tasten belegen", 1),
                            ("Tastatur && Profile", 2)):
            button = QPushButton(name)
            button.clicked.connect(lambda checked=False, target=index: self.navigate.emit(target))
            actions.addWidget(button)
        layout.addLayout(actions)
        note = QLabel(
            "Alle Einstellungen bleiben lokal gespeichert. L1 wechselt den Bildschirm; "
            "L2–L5 führen seine Funktionen aus.")
        note.setWordWrap(True)
        note.setObjectName("Status")
        layout.addWidget(note)
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.refresh)

    def refresh(self):
        try:
            screens = load_screens()
            number = read_screen()
            self.screen_name.setText(screens[number])
            self.screen_count.setText(str(len(screens)))
            pixmap, _, error = render_preview(number, tag="overview")
            self.preview.set_data(pixmap, [])
            self.error.setText(error or "")
        except (OSError, ValueError) as error:
            self.screen_name.setText("Nicht verfügbar")
            self.screen_count.setText("Nicht verfügbar")
            self.preview.set_data(None, [])
            self.error.setText(f"Übersicht konnte nicht geladen werden: {error}")

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()
        self.timer.start()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Logitech G510s Steuerung")
        self.setStyleSheet(STYLESHEET)

        self.keyboard_tab = KeyboardTab()
        self.custom_tab = CustomScreensTab()

        self.overview_tab = OverviewTab()
        self.logos_tab = GameLogosTab()
        self.page_widgets = [self.overview_tab, self.custom_tab,
                             self.keyboard_tab, self.logos_tab]
        titles = ["Übersicht", "LCD-Bildschirme", "Tastatur & Profile",
                  "Spiel-Logos"]
        descriptions = [
            "Deine Tastatur und die aktuelle LCD-Anzeige im Überblick.",
            "Bildschirm gestalten und die Funktionen von L2 bis L5 direkt unter der Vorschau festlegen.",
            "Beleuchtung, Profile und G-Tasten-Makros verwalten.",
            "Automatische Spielanzeigen und eigene Logos verwalten.",
        ]
        shell = QWidget()
        root = QHBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(210)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(14, 24, 14, 14)
        brand = QLabel("G510s")
        brand.setObjectName("Brand")
        side.addWidget(brand)
        side.addWidget(QLabel("STEUERUNG"))
        side.addSpacing(24)
        self.navigation = QListWidget()
        self.navigation.setObjectName("Navigation")
        self.navigation.addItems(titles)
        side.addWidget(self.navigation, 1)
        footer = QLabel("Logitech G510s\nLCD · RGB · Makros\n\nF11  Vollbild\nEsc  Vollbild verlassen")
        footer.setObjectName("Status")
        side.addWidget(footer)
        root.addWidget(sidebar)
        content = QVBoxLayout()
        content.setContentsMargins(20, 18, 20, 8)
        header = QHBoxLayout()
        headings = QVBoxLayout()
        self.page_title = QLabel()
        self.page_title.setObjectName("PageTitle")
        self.page_description = QLabel()
        self.page_description.setWordWrap(True)
        self.page_description.setObjectName("Status")
        headings.addWidget(self.page_title)
        headings.addWidget(self.page_description)
        header.addLayout(headings, 1)
        self.fullscreen_button = QPushButton("Vollbild · F11")
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        header.addWidget(self.fullscreen_button)
        content.addLayout(header)
        self.pages = QStackedWidget()
        for page in self.page_widgets:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setWidget(page)
            self.pages.addWidget(scroll)
        content.addWidget(self.pages, 1)
        root.addLayout(content, 1)
        self.setCentralWidget(shell)

        def select_page(index):
            self.pages.setCurrentIndex(index)
            self.page_title.setText(titles[index])
            self.page_description.setText(descriptions[index])

        self.navigation.currentRowChanged.connect(select_page)
        self.overview_tab.navigate.connect(self.navigation.setCurrentRow)
        self.navigation.setCurrentRow(0)
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)
        QShortcut(QKeySequence("Escape"), self, activated=self.leave_fullscreen)
        self._restore_maximized = False

        # Direct request: "make me a save button/feature o dont trust
        # my settings will survive reboots" -- every individual action
        # in this app (dragging an element, clicking Apply/Set as
        # Default, recording a macro) already writes straight to disk
        # immediately, so there was never actually a missing autosave
        # path to add. What WAS missing is visible proof of that: this
        # button re-saves everything explicitly, then reads each file
        # straight back off disk and compares it against what's
        # supposed to be there -- a real verification, not just "the
        # write call didn't throw" -- and reports exactly what it
        # confirmed (or, honestly, what failed) in the status bar. A
        toolbar = self.addToolBar("Speichern")
        self.addToolBar(Qt.BottomToolBarArea, toolbar)
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        # Direct report: "the 'save all settings now' button has a
        # weird rectangle icon before it" -- the floppy-disk emoji
        # (U+1F4BE) has no matching glyph in this system's font stack,
        # so it rendered as a tofu box instead. Plain text avoids the
        # font-coverage gamble entirely.
        self.save_all_btn = QPushButton("Alle Einstellungen jetzt speichern")
        self.save_all_btn.setObjectName("saveAllBtn")
        self.save_all_btn.setToolTip("Speichert alles erneut und prüft, ob es korrekt von der Festplatte zurückgelesen wird – alles wird bereits automatisch gespeichert, das hier bestätigt es nur")
        self.save_all_btn.clicked.connect(self.on_save_all)
        saved_hint = QLabel("Änderungen werden automatisch gespeichert.")
        saved_hint.setObjectName("Status")
        toolbar.addWidget(saved_hint)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)
        toolbar.addWidget(self.save_all_btn)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage(
            "Bereit · Einstellungen lokal gespeichert · F11: Vollbild"
        )

        self.setMinimumSize(900, 580)
        available = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1440, available.width()), min(900, available.height()))

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.leave_fullscreen()
        else:
            self._restore_maximized = self.isMaximized()
            self.showFullScreen()

    def leave_fullscreen(self):
        if self.isFullScreen():
            if self._restore_maximized:
                self.showMaximized()
            else:
                self.showNormal()

    def changeEvent(self, event):
        super().changeEvent(event)
        if hasattr(self, "fullscreen_button"):
            self.fullscreen_button.setText(
                "Vollbild verlassen · F11" if self.isFullScreen() else "Vollbild · F11")

    def on_save_all(self):
        """Real disk round-trip verification, not a cosmetic no-op:
        re-writes each real data store this app owns, then reads it
        back off disk and checks it actually matches, so "Saved" here
        means "confirmed on disk right now", not just "the write call
        didn't raise". Direct feedback on the first version of this
        button: "kinda sucks, offers no assurance anything is saved" --
        a status-bar line at the bottom of the window is too easy to
        miss entirely. This now pops a modal confirmation dialog (can't
        be missed, has to be dismissed) that itemizes exactly what got
        verified PER SCREEN -- also directly answers "does it also save
        the L screens?": yes, `self.custom_tab.config` already holds
        every editable screen in one dict, saved/reloaded together, so
        the breakdown below always lists all of them, even ones with 0
        elements, as visible proof none were silently skipped."""
        problems = []
        detail_lines = []

        # 1. Custom Screens -- ALL screens (L2, L3, L4, L5) live in one
        # config dict and save_custom_screens()/load_custom_screens()
        # always write/read the whole thing together, never a single
        # screen in isolation, so there's no way for this to silently
        # save only the currently-open one.
        try:
            save_custom_screens(self.custom_tab.config)
            reloaded = load_custom_screens()
            if reloaded != self.custom_tab.config:
                problems.append("Eigene Bildschirme: gespeichert, aber nicht identisch zurückgelesen")
            else:
                for screen in sorted(self.custom_tab.config.keys()):
                    n = len(self.custom_tab.config[screen])
                    detail_lines.append(f"    {screen}: {n} Element(e)")
        except OSError as e:
            problems.append(f"Eigene Bildschirme: {e}")

        # 2. Backlight boot default (set-backlight-color.sh). Apply and
        # Set as Default both already write this immediately -- this
        # re-persists whatever color is CURRENTLY shown/pending so even
        # an in-progress pick gets a real boot-default, then verifies
        # the exact RGB triple is really in the file on disk.
        try:
            rgb = self.keyboard_tab._pending_rgb
            set_as_default(rgb)
            on_disk = DEFAULTS_SCRIPT_DATA_DIR.read_text()
            if f"{rgb[0]} {rgb[1]} {rgb[2]}" not in on_disk:
                problems.append("Beleuchtung: gespeichert, aber nicht identisch zurückgelesen")
            else:
                detail_lines.append(f"    Startfarbe: #{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}")
        except OSError as e:
            problems.append(f"Beleuchtung: {e}")

        # 3. Macros -- each one already writes to macros.json the
        # instant it's recorded (no separate in-memory "pending" macro
        # state exists to re-save), so this is a read-back sanity check
        # only: confirm the file exists, is valid JSON, and count what's
        # actually assigned per profile.
        try:
            macro_counts = {}
            if MACROS_FILE.exists():
                data = json.loads(MACROS_FILE.read_text())
                for profile, keys in data.items():
                    if keys:
                        macro_counts[profile] = len(keys)
            if macro_counts:
                for profile in sorted(macro_counts):
                    detail_lines.append(f"    {profile}: {macro_counts[profile]} Makro(s) zugewiesen")
            else:
                detail_lines.append("    (noch keine Makros zugewiesen)")
        except (OSError, json.JSONDecodeError) as e:
            problems.append(f"Makros: {e}")

        try:
            if self.custom_tab.key_bindings is None:
                problems.append("LCD-Tasten: Belegung konnte nicht geladen werden")
            elif load_bindings() != self.custom_tab.key_bindings:
                problems.append("LCD-Tasten: gespeicherte Belegung weicht von der Anzeige ab")
            else:
                detail_lines.append("    LCD-Tasten: Belegung bestätigt")
        except (OSError, ValueError) as error:
            problems.append(f"LCD-Tasten: {error}")

        selected_screen = None
        try:
            active_tab = self.page_widgets[self.pages.currentIndex()]
            if active_tab is self.custom_tab:
                selected_screen = self.custom_tab.apply_selected_screen()
        except (OSError, ValueError) as error:
            problems.append(f"Bildschirmwechsel: {error}")

        now = datetime.datetime.now().strftime("%H:%M:%S")
        if problems:
            msg = "Speichern FEHLGESCHLAGEN um " + now + ":\n\n" + "\n".join(problems)
            self.status.showMessage("✗ " + msg.replace("\n", " "))
            QMessageBox.critical(self, "Speichern fehlgeschlagen", msg)
        else:
            msg = (
                f"Auf der Festplatte bestätigt um {now}:\n\n"
                "Eigene Bildschirme:\n" + "\n".join(detail_lines[:len(self.custom_tab.config)]) + "\n\n"
                "Beleuchtung + Makros:\n" + "\n".join(detail_lines[len(self.custom_tab.config):])
            )
            if selected_screen is not None:
                msg += f"\n\nLCD-Bildschirm ausgewählt: {selected_screen}"
            self.status.showMessage(f"✓ Um {now} gespeichert und auf der Festplatte bestätigt")
            QMessageBox.information(self, "Gespeichert", msg)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    icon_path = PROJECT_DIR / "assets" / "icon" / "g510-lcd.png"
    app.setWindowIcon(QIcon(str(icon_path)))
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
