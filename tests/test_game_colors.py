"""Temporary game-color policy, persistence, process lifetime and GUI controls."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import g510_game_colors as colors


class GameColorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "game_colors.json"
        self.apply = Mock()
        self.restore = Mock()
        self.controller = colors.ColorController(self.apply, self.restore)
        self.colors = {"10": [255, 0, 0], "20": [0, 0, 255]}
        self.games = {100: 10, 101: 10, 200: 20, 300: 30}

    def test_switch_focused_games_keep_color_on_desktop_restore_at_exit(self):
        self.controller.update(self.colors, self.games, 100)
        self.apply.assert_called_once_with((255, 0, 0))
        self.controller.update(self.colors, self.games, 999)
        self.assertEqual(self.apply.call_count, 1)
        self.restore.assert_not_called()
        self.controller.update(self.colors, self.games, 200)
        self.apply.assert_called_with((0, 0, 255))
        self.controller.update(self.colors, {100: 10}, 999)
        self.restore.assert_called_once()
        self.controller.update(self.colors, {}, 0)
        self.restore.assert_called_once()

    def test_uncolored_game_does_not_change_existing_game_color(self):
        self.controller.update(self.colors, self.games, 100)
        self.controller.update(self.colors, self.games, 300)
        self.restore.assert_not_called()
        self.assertEqual(self.controller.owner, 10)
        self.assertEqual(self.apply.call_count, 1)

    def test_game_lifetime_is_not_tied_to_audio_or_one_child_process(self):
        self.controller.update(self.colors, self.games, 100)
        self.controller.update(self.colors, {101: 10}, 0)
        self.restore.assert_not_called()
        self.controller.update(self.colors, {}, 0)
        self.restore.assert_called_once()

    def test_edit_remove_color_and_shutdown_restore_default(self):
        self.controller.update(self.colors, self.games, 100)
        self.controller.update({"10": [0, 255, 0]}, self.games, 100)
        self.apply.assert_called_with((0, 255, 0))
        self.controller.update({}, self.games, 100)
        self.restore.assert_called_once()
        self.controller.update(self.colors, self.games, 200)
        self.controller.close()
        self.assertEqual(self.restore.call_count, 2)
        self.controller.close()
        self.assertEqual(self.restore.call_count, 2)

    def test_failed_led_or_restore_can_be_retried_without_losing_state(self):
        self.apply.side_effect = PermissionError("denied")
        with self.assertRaises(PermissionError):
            self.controller.update(self.colors, self.games, 100)
        self.assertIsNone(self.controller.owner)
        self.apply.side_effect = None
        self.controller.update(self.colors, self.games, 100)
        self.restore.side_effect = OSError("missing")
        with self.assertRaises(OSError):
            self.controller.update({}, {}, 0)
        self.assertEqual(self.controller.owner, 10)
        self.restore.side_effect = None
        self.controller.update({}, {}, 0)
        self.assertIsNone(self.controller.owner)

    def test_persistence_preserves_other_games_and_never_writes_standard(self):
        standard = self.root / "set-backlight-color.sh"
        standard.write_text("unchanged")
        colors.save_color(10, (255, 0, 12), self.path)
        colors.save_color(20, (0, 0, 0), self.path)
        self.assertEqual(colors.load_colors(self.path), {"10": [255, 0, 12], "20": [0, 0, 0]})
        colors.save_color(10, None, self.path)
        self.assertEqual(colors.load_colors(self.path), {"20": [0, 0, 0]})
        self.assertEqual(standard.read_text(), "unchanged")

    def test_standard_color_parser_does_not_execute_script(self):
        path = self.root / "standard.sh"
        path.write_text(
            '#!/bin/bash\necho "0 255 0" > /sys/class/leds/g15::kbd_backlight/multi_intensity\n'
            'exit 99\n')
        self.assertEqual(colors.load_standard_color(path), (0, 255, 0))
        path.write_text('echo "999 0 0" > /sys/class/leds/g15::kbd_backlight/multi_intensity\n')
        with self.assertRaises(ValueError):
            colors.load_standard_color(path)
        path.unlink()
        self.assertIsNone(colors.load_standard_color(path))

    def test_keyboard_picker_uses_saved_standard_not_temporary_game_color(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtCore import QEvent
        from PyQt5.QtWidgets import QApplication
        import g510_app as gui
        app = QApplication.instance() or QApplication([])
        with patch.object(gui, "read_current_rgb", return_value=(255, 0, 0)), \
                patch.object(colors, "load_standard_color", return_value=(0, 255, 0)):
            tab = gui.KeyboardTab()
        self.assertEqual(tab._pending_rgb, (0, 255, 0))
        tab.close()
        tab.deleteLater()
        app.sendPostedEvents(None, QEvent.DeferredDelete)

    def test_corrupt_config_is_reported_not_replaced(self):
        for content in ('[]', '{"10":[1,2]}', '{"10":[true,2,3]}',
                        '{"x":[1,2,3]}', '{"10":[256,2,3]}', '{broken'):
            self.path.write_text(content)
            with self.subTest(config=content), self.assertRaises(ValueError):
                colors.save_color(20, (1, 2, 3), self.path)
            self.assertEqual(self.path.read_text(), content)

    def test_process_scan_handles_steam_ids_zombies_and_races(self):
        def process(pid, environment, state="S"):
            directory = self.root / str(pid)
            directory.mkdir()
            (directory / "environ").write_bytes(environment)
            (directory / "status").write_text(f"State:\t{state} (fixture)\n")
        process(100, b"OTHER=foo\0SteamAppId=10\0")
        process(101, b"STEAM_COMPAT_APP_ID=20\0")
        process(102, b"SteamGameId=30\0", "Z")
        process(103, b"SteamAppId=0\0SteamGameId=40\0")
        process(104, b"SteamAppId=notanumber\0")
        (self.root / "105").mkdir()
        self.assertEqual(colors.process_games(self.root), {100: 10, 101: 20, 103: 40})

    def test_gui_saves_color_cancel_remove_and_errors_without_applying_led(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtCore import QEvent
        from PyQt5.QtGui import QColor
        from PyQt5.QtWidgets import QApplication
        import g510_app as gui
        app = QApplication.instance() or QApplication([])
        with patch.object(colors, "CONFIG_PATH", self.path), \
                patch.object(gui, "DATA_DIR", self.root):
            tab = gui.GameLogosTab()
            tab.games = {10: "Game"}
            tab.fill_list()
            tab.list.setCurrentRow(0)
            with patch.object(gui.QColorDialog, "getColor", return_value=QColor("#123456")), \
                    patch.object(colors, "apply_color") as apply:
                tab.choose_game_color()
                apply.assert_not_called()
            self.assertEqual(colors.load_colors(), {"10": [18, 52, 86]})
            self.assertIn("#123456", tab.game_color_label.text())
            with patch.object(gui.QColorDialog, "getColor", return_value=QColor()):
                tab.choose_game_color()
            self.assertEqual(colors.load_colors(), {"10": [18, 52, 86]})
            with patch.object(colors, "save_color", side_effect=PermissionError("fixture")), \
                    patch.object(gui.QMessageBox, "warning") as warning:
                tab.clear_game_color()
            warning.assert_called_once()
            self.assertIn("#123456", tab.game_color_label.text())
            tab.clear_game_color()
            self.assertEqual(colors.load_colors(), {})
            self.assertFalse(tab.clear_game_color_button.isEnabled())
            tab.close()
            tab.deleteLater()
            app.sendPostedEvents(None, QEvent.DeferredDelete)
