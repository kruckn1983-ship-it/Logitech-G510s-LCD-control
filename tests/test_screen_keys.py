import json
import os
from pathlib import Path
import subprocess
import shutil
import struct
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import g510_screen_keys as keys


class ScreenKeyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / "keys.json"
        catalog = patch.object(keys, "SCREENS_PATH", self.root / "screens.json")
        catalog.start()
        self.addCleanup(catalog.stop)
        clock = patch.object(keys, "CLOCK_LAYOUT_PATH", self.root / "clock_layout")
        clock.start()
        self.addCleanup(clock.stop)
        self.env = patch.dict(os.environ, XDG_RUNTIME_DIR=str(self.root))
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_cycle_includes_clock_and_wraps(self):
        self.assertEqual([keys.next_screen(n) for n in (0, 2, 3, 4, 5, 1)],
                         [3, 3, 4, 5, 1, 2])

    def test_defaults_and_persistence(self):
        data = keys.load_bindings(self.config)
        self.assertEqual(list(data["3"].values()), ["previous", "next", "play", "pause"])
        self.assertTrue(all(action == "none" for screen, mapping in data.items()
                            if screen not in ("1", "3") for action in mapping.values()))
        self.assertEqual(list(data["1"].values()), ["clock_previous", "clock_next", "none", "none"])
        data["2"]["L2"] = "mute"
        keys.save_bindings(data, self.config)
        self.assertEqual(keys.load_bindings(self.config), data)

    def test_invalid_config_explicitly_fails(self):
        for data in ("not json", "[]", '{"3":{}}'):
            self.config.write_text(data)
            with self.assertRaises(ValueError):
                keys.load_bindings(self.config)
        data = keys.default_bindings()
        data["2"]["L2"] = "rm -rf something"
        self.config.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            keys.load_bindings(self.config)

    def test_clock_keys_cycle_all_20_designs_both_directions_and_persist(self):
        keys.show_screen(1)
        self.assertEqual(keys.load_clock_layout(), 0)
        with patch.object(keys, "load_bindings", return_value=keys.default_bindings()), \
                patch.object(keys.subprocess, "run") as run:
            observed = []
            for _ in range(21):
                keys.handle_key("L3")
                observed.append(keys.load_clock_layout())
            self.assertEqual(observed, list(range(1, 20)) + [0, 1])
            keys.handle_key("L2")
            self.assertEqual(keys.load_clock_layout(), 0)
            keys.handle_key("L2")
            self.assertEqual(keys.load_clock_layout(), 19)
            self.assertEqual(keys.read_screen(), 1)
            self.assertEqual(keys.CLOCK_LAYOUT_PATH.read_text(), "19\n")
            run.assert_not_called()
            keys.handle_key("L1")
            self.assertEqual(keys.read_screen(), 2)
            self.assertEqual(keys.load_clock_layout(), 19)

    def test_clock_actions_outside_clock_and_invalid_state_explicitly_fail(self):
        keys.show_screen(2)
        with self.assertRaisesRegex(ValueError, "aktiven Uhr"):
            keys.perform_action("clock_next")
        self.assertFalse(keys.CLOCK_LAYOUT_PATH.exists())
        for value in ("", "-1", "20", "1.5", "x", "1\n2", "９"):
            keys.CLOCK_LAYOUT_PATH.write_text(value)
            with self.assertRaises(ValueError):
                keys.load_clock_layout()
        for value in (-1, 20, True, "2"):
            with self.assertRaises(ValueError):
                keys.save_clock_layout(value)
        keys.show_screen(1)
        with self.assertRaises(ValueError):
            keys.perform_action("clock_next")
        keys.CLOCK_LAYOUT_PATH.unlink()
        keys.save_clock_layout(7)
        self.assertEqual(keys.load_clock_layout(), 7)
        self.assertFalse(keys.CLOCK_LAYOUT_PATH.with_suffix(".tmp").exists())

    def test_existing_explicit_clock_key_bindings_remain_unchanged(self):
        data = keys.default_bindings()
        data["1"].update(L2="volume_down", L3="none")
        keys.save_bindings(data, self.config)
        self.assertEqual(keys.load_bindings(self.config)["1"], data["1"])

    def test_l1_sets_manual_override_even_when_target_matches_auto_screen(self):
        (self.root / "g510lcd_screen").write_text("2")
        keys.handle_key("L1")
        self.assertEqual(keys.read_screen(), 3)
        self.assertEqual((self.root / "g510lcd_manual_screen").read_text(), "1")

    def test_bindings_are_screen_specific_and_reloaded_per_press(self):
        keys.show_screen(3)
        data = keys.default_bindings()
        with patch.object(keys, "load_bindings", return_value=data), \
                patch.object(keys, "perform_action") as action:
            keys.handle_key("L2")
            action.assert_called_with("previous")
            data["3"]["L2"] = "play_pause"
            keys.handle_key("L2")
            action.assert_called_with("play_pause")
            keys.show_screen(2)
            keys.handle_key("L2")
            action.assert_called_with("none")

    def test_player_selection_prefers_active_and_uses_single_instance(self):
        output = ("vlc\x1fPaused\nbrave.instance10\x1fPlaying\n"
                  "plasma-browser-integration.instance2\x1fPlaying\n")
        with patch.object(keys.subprocess, "run", return_value=
                          subprocess.CompletedProcess([], 0, output, "")) as run:
            keys.perform_action("pause")
            self.assertEqual(run.call_args.args[0],
                             ["playerctl", "-p", "plasma-browser-integration.instance2", "pause"])

    def test_no_player_and_failed_actions_are_not_hidden(self):
        with patch.object(keys.subprocess, "run",
                          return_value=subprocess.CompletedProcess([], 0, "", "")):
            with self.assertRaises(RuntimeError):
                keys.perform_action("play")
        with patch.object(keys.subprocess, "run",
                          side_effect=subprocess.TimeoutExpired("playerctl", 3)):
            with self.assertRaises(subprocess.TimeoutExpired):
                keys.perform_action("play")

    def test_volume_and_noop_do_not_invoke_media_player(self):
        with patch.object(keys.subprocess, "run") as run:
            keys.perform_action("none")
            run.assert_not_called()
            keys.perform_action("volume_down")
            self.assertEqual(run.call_args.args[0],
                             ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-5%"])
        keys.perform_action("screen_5")
        self.assertEqual(keys.read_screen(), 5)

    def test_legacy_and_invalid_screen(self):
        self.assertEqual(keys.read_screen(), 2)
        (self.root / "g510lcd_screen").write_text("0")
        self.assertEqual(keys.read_screen(), 2)
        (self.root / "g510lcd_screen").write_text("9")
        with self.assertRaises(ValueError):
            keys.read_screen()

    def test_gui_saves_per_screen_without_executing_actions(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication
        from g510_key_settings import ScreenKeysTab
        app = QApplication.instance() or QApplication([])
        with patch("g510_key_settings.load_bindings", return_value=keys.default_bindings()), \
                patch("g510_key_settings.save_bindings") as save, \
                patch("g510_key_settings.show_screen") as show:
            tab = ScreenKeysTab()
            tab.screen.setCurrentIndex(tab.screen.findData(3))
            save.assert_not_called()
            tab.combos["L2"].setCurrentIndex(tab.combos["L2"].findData("mute"))
            tab.save()
            self.assertEqual(save.call_args.args[0]["3"]["L2"], "mute")
            self.assertEqual(save.call_args.args[0]["2"]["L2"], "none")
            show.assert_not_called()
            tab.show_selected()
            show.assert_called_once_with(3)
            self.assertFalse(tab.combos["L2"].model().item(
                tab.combos["L2"].findData("clock_next")).isEnabled())
            tab.screen.setCurrentIndex(tab.screen.findData(1))
            self.assertEqual(tab.combos["L2"].currentData(), "clock_previous")
            self.assertTrue(tab.combos["L2"].model().item(
                tab.combos["L2"].findData("clock_next")).isEnabled())
            tab.close()
        self.assertIsNotNone(app)


class ButtonListenerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.directory = Path(cls.tmp.name)
        source = Path(__file__).resolve().parents[1] / "src"
        harness = cls.directory / "listener.c"
        harness.write_text(
            '#include <stdio.h>\n'
            'static FILE *test_fopen(const char *, const char *);\n'
            '#define fopen test_fopen\n'
            f'#include "{source / "g510_lcd_buttons.c"}"\n'
            '#undef fopen\n'
            'static FILE *test_fopen(const char *path, const char *mode) {\n'
            ' return fopen(strcmp(path, "/dev/g510-keys") == 0 ? getenv("EVENTS") : path, mode);\n'
            '}\n'
        )
        subprocess.run(["gcc", "-Wall", "-Wextra", "-Werror", str(harness),
                        "-o", str(cls.directory / "listener")], check=True)
        shutil.copy2(source / "g510_screen_keys.py", cls.directory)

    def test_physical_key_dispatch_cycle_and_bounce_filter(self):
        with tempfile.TemporaryDirectory() as home:
            runtime = Path(home)
            events = runtime / "events"
            # A repeat event and a second bouncing key-down must not advance L1.
            events.write_bytes(b"".join(struct.pack("@llHHi", 0, 0, 1, 696, value)
                                       for value in (1, 2, 1, 0)))
            env = dict(os.environ, HOME=home, XDG_RUNTIME_DIR=home, EVENTS=str(events))
            observed = []
            for _ in range(5):
                subprocess.run([str(self.directory / "listener")], env=env, check=True)
                observed.append((runtime / "g510lcd_screen").read_text())
            self.assertEqual(observed, ["3", "4", "5", "1", "2"])

    def test_unassigned_key_does_not_switch_screen(self):
        with tempfile.TemporaryDirectory() as home:
            runtime = Path(home)
            (runtime / "g510lcd_screen").write_text("2")
            events = runtime / "events"
            events.write_bytes(struct.pack("@llHHi", 0, 0, 1, 697, 1))
            env = dict(os.environ, HOME=home, XDG_RUNTIME_DIR=home, EVENTS=str(events))
            subprocess.run([str(self.directory / "listener")], env=env, check=True)
            self.assertEqual((runtime / "g510lcd_screen").read_text(), "2")

    def test_physical_clock_keys_change_layout_without_changing_screen(self):
        with tempfile.TemporaryDirectory() as home:
            runtime = Path(home)
            (runtime / "g510lcd_screen").write_text("1")
            events = runtime / "events"
            env = dict(os.environ, HOME=home, XDG_RUNTIME_DIR=home, EVENTS=str(events))
            layout = runtime / ".local/share/g510-lcd/clock_layout"
            for code, expected in ((698, "1\n"), (697, "0\n"), (697, "19\n")):
                events.write_bytes(struct.pack("@llHHi", 0, 0, 1, code, 1))
                subprocess.run([str(self.directory / "listener")], env=env, check=True)
                self.assertEqual(layout.read_text(), expected)
                self.assertEqual((runtime / "g510lcd_screen").read_text(), "1")

    def test_single_live_key_press_is_processed_before_stream_closes(self):
        with tempfile.TemporaryDirectory() as home:
            runtime = Path(home)
            events = runtime / "events"
            os.mkfifo(events)
            env = dict(os.environ, HOME=home, XDG_RUNTIME_DIR=home, EVENTS=str(events))
            process = subprocess.Popen([str(self.directory / "listener")], env=env)
            try:
                with events.open("wb", buffering=0) as writer:
                    writer.write(struct.pack("@llHHi", 0, 0, 1, 696, 1))
                    state = runtime / "g510lcd_screen"
                    deadline = time.monotonic() + 2
                    while not state.exists() and time.monotonic() < deadline:
                        time.sleep(0.01)
                    self.assertTrue(state.exists(), "L1 must work without further events or EOF")
                    self.assertEqual(state.read_text(), "3")
                    self.assertIsNone(process.poll())
                self.assertEqual(process.wait(timeout=3), 0)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()


class ScreenSelectionGuiTests(unittest.TestCase):
    def test_editor_selection_and_save_apply_screen(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication
        import g510_app as gui
        app = QApplication.instance() or QApplication([])
        # Exercise the real selection and save handlers without touching user settings.
        from types import SimpleNamespace
        config = {key: [] for key in gui.CUSTOM_SCREEN_KEYS}
        custom = SimpleNamespace(
            config=config, current_screen="L3",
            apply_selected_screen=lambda: gui.CustomScreensTab.apply_selected_screen(custom),
            screen_number=lambda: 3)
        with patch.object(gui, "show_screen") as show, \
                patch.object(gui, "read_screen", return_value=3):
            self.assertEqual(custom.apply_selected_screen(), "Media Center")
            show.assert_called_once_with(3)
        with patch.object(gui, "show_screen"), \
                patch.object(gui, "read_screen", return_value=2):
            with self.assertRaises(OSError):
                custom.apply_selected_screen()
        with tempfile.TemporaryDirectory() as directory:
            defaults = Path(directory) / "color.sh"
            defaults.write_text("1 2 3")
            window = SimpleNamespace(
                custom_tab=custom,
                keyboard_tab=SimpleNamespace(_pending_rgb=(1, 2, 3)),
                keys_tab=SimpleNamespace(bindings=keys.default_bindings()),
                page_widgets=[custom],
                pages=SimpleNamespace(currentIndex=lambda: 0),
                status=SimpleNamespace(showMessage=Mock()))
            with patch.object(gui, "show_screen") as show, \
                    patch.object(gui, "read_screen", return_value=3), \
                    patch.object(gui, "save_custom_screens"), \
                    patch.object(gui, "load_custom_screens", return_value=config), \
                    patch.object(gui, "set_as_default"), \
                    patch.object(gui, "DEFAULTS_SCRIPT_DATA_DIR", defaults), \
                    patch.object(gui, "MACROS_FILE", Path(directory) / "missing.json"), \
                    patch.object(gui, "load_bindings", return_value=keys.default_bindings()), \
                    patch.object(gui.QMessageBox, "information") as information, \
                    patch.object(gui.QMessageBox, "critical") as critical:
                gui.MainWindow.on_save_all(window)
                show.assert_called_once_with(3)
                critical.assert_not_called()
                self.assertIn("LCD-Bildschirm ausgewählt: Media Center",
                              information.call_args.args[2])
                information.reset_mock()
                with patch.object(gui, "read_screen", return_value=2):
                    gui.MainWindow.on_save_all(window)
                critical.assert_called_once()
                information.assert_not_called()
                window.keys_tab.screen = SimpleNamespace(
                    currentData=lambda: 4, currentText=lambda: "Spiele")
                window.page_widgets = [window.keys_tab]
                show.reset_mock()
                critical.reset_mock()
                with patch.object(gui, "read_screen", return_value=4):
                    gui.MainWindow.on_save_all(window)
                show.assert_called_once_with(4)
                critical.assert_not_called()
                self.assertIn("LCD-Bildschirm ausgewählt: Spiele",
                              information.call_args.args[2])
                show.reset_mock()
                window.page_widgets = [window.keyboard_tab]
                gui.MainWindow.on_save_all(window)
                show.assert_not_called()
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
