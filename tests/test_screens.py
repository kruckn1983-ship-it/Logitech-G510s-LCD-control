"""Dynamic screen catalog, editor and key settings regressions."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import g510_screen_keys as keys


class ScreenCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.catalog = self.root / ".local/share/g510-lcd/screens.json"
        self.bindings_file = self.catalog.with_name("lcd_keys.json")
        for context in (
                patch.object(keys, "SCREENS_PATH", self.catalog),
                patch.dict(os.environ, XDG_RUNTIME_DIR=str(self.root))):
            context.start()
            self.addCleanup(context.stop)

    def catalog_with(self, count):
        return {"next_id": 6 + count,
                "screens": [{"id": n, "name": f"Screen {n}"}
                            for n in range(6, 6 + count)]}

    def test_many_screens_persist_cycle_and_direct_actions(self):
        keys.save_screen_catalog(self.catalog_with(80))
        screens = keys.load_screens()
        self.assertEqual(len(screens), 85)
        self.assertEqual(keys.next_screen(1), 6)
        self.assertEqual(keys.next_screen(85), 2)
        self.assertEqual(keys.next_screen(9), 10)
        keys.perform_action("screen_12")
        self.assertEqual(keys.read_screen(), 12)
        with patch.object(keys, "load_bindings",
                          return_value=keys.default_bindings()):
            keys.handle_key("L1")
        self.assertEqual(keys.read_screen(), 13)
        result = subprocess.check_output(
            [sys.executable, "-c",
             "import g510_screen_keys as k; print(len(k.load_screens()), k.next_screen(85))"],
            env=dict(os.environ, HOME=str(self.root),
                     PYTHONPATH=str(Path(keys.__file__).parent)), text=True)
        self.assertEqual(result.strip(), "85 2")

    def test_old_bindings_gain_defaults_and_deleted_targets_are_unbound(self):
        old = keys.default_bindings()
        keys.save_bindings(old, self.bindings_file)
        catalog = self.catalog_with(7)
        keys.save_screen_catalog(catalog)
        bindings = keys.load_bindings(self.bindings_file)
        self.assertEqual(bindings["12"], dict.fromkeys(("L2", "L3", "L4", "L5"), "none"))
        bindings["2"]["L3"] = "screen_12"
        bindings["12"]["L2"] = "mute"
        keys.save_bindings(bindings, self.bindings_file)
        self.assertEqual(keys.load_bindings(self.bindings_file), bindings)
        with patch.object(keys, "load_bindings", return_value=bindings), \
                patch.object(keys, "perform_action") as action:
            keys.show_screen(12)
            keys.handle_key("L2")
            action.assert_called_once_with("mute")
        catalog["screens"].pop()
        keys.save_screen_catalog(catalog)
        loaded = keys.load_bindings(self.bindings_file)
        self.assertNotIn("12", loaded)
        self.assertEqual(loaded["2"]["L3"], "none")
        self.assertEqual(loaded["3"], old["3"])
        self.assertEqual(keys.load_screen_catalog()["next_id"], 13)

    def test_bad_catalog_is_reported_not_replaced(self):
        valid = self.catalog_with(2)
        invalid = [
            [], {"screens": [], "next_id": 2},
            {**valid, "screens": [valid["screens"][0]] * 2},
            {"screens": [{"id": 6, "name": "System"}], "next_id": 7},
            {"screens": [{"id": 6, "name": "bad\nname"}], "next_id": 7},
            {"screens": [{"id": True, "name": "Test"}], "next_id": 7},
        ]
        self.catalog.parent.mkdir(parents=True)
        for value in invalid:
            with self.subTest(value=value):
                content = json.dumps(value)
                self.catalog.write_text(content)
                with self.assertRaises(ValueError):
                    keys.load_screens()
                self.assertEqual(self.catalog.read_text(), content)

    def test_editor_dropdown_create_rename_delete_and_reload(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication, QMessageBox
        import g510_app as gui
        app = QApplication.instance() or QApplication([])
        self.catalog.parent.mkdir(parents=True)
        layout = self.catalog.with_name("custom_screens.txt")
        layout.write_text("SCREEN L2\nTEXT content2=Keep x=2 y=2 font=0\n")
        contexts = (
            patch.object(gui, "CUSTOM_SCREENS_FILE", layout),
            patch.object(gui, "DATA_DIR", self.catalog.parent),
            patch.object(gui.CustomScreensTab, "refresh_preview"),
            patch.object(gui, "load_bindings",
                         side_effect=lambda: keys.load_bindings(self.bindings_file)),
            patch.object(gui.QMessageBox, "critical",
                         side_effect=AssertionError("Unexpected GUI error")),
        )
        for context in contexts:
            context.start()
            self.addCleanup(context.stop)
        tab = gui.CustomScreensTab()
        before = tab.config["L2"]
        self.assertFalse(hasattr(tab, "screen_buttons"))
        for number in range(6, 36):
            with patch.object(gui.QInputDialog, "getText",
                              return_value=(f"My Screen {number}", True)):
                tab.add_screen()
            self.assertEqual(tab.screen_number(), number)
            self.assertEqual(keys.read_screen(), number)
        self.assertEqual(tab.screen_combo.count(), 35)
        tab.populate_function_menu("L2")
        self.assertIn("screen_35", [
            item.data() for item in tab.function_menu_buttons["L2"].menu().actions()])
        self.assertEqual(tab.config["L2"], before)
        catalog_before = self.catalog.read_text()
        layout_before = layout.read_text()
        for invalid_name in ("", "System", "bad\nname"):
            with patch.object(gui.QInputDialog, "getText",
                              return_value=(invalid_name, True)), \
                    patch.object(gui.QMessageBox, "critical") as error:
                tab.add_screen()
                error.assert_called_once()
            self.assertEqual(self.catalog.read_text(), catalog_before)
            self.assertEqual(layout.read_text(), layout_before)
        with patch.object(gui.QInputDialog, "getText", return_value=("Unsaved", True)), \
                patch.object(gui, "save_screen_catalog", side_effect=OSError("read only")), \
                patch.object(gui.QMessageBox, "critical") as error:
            tab.add_screen()
            error.assert_called_once()
        self.assertEqual(self.catalog.read_text(), catalog_before)
        self.assertEqual(layout.read_text(), layout_before)
        self.assertEqual(tab.screen_combo.count(), 35)
        with patch.object(gui.QInputDialog, "getText", return_value=("Renamed", True)):
            tab.rename_screen()
        self.assertEqual(tab.screen_combo.currentText(), "Renamed")
        tab.populate_function_menu("L2")
        self.assertEqual(next(item.text() for item in tab.function_menu_buttons["L2"].menu().actions()
                              if item.data() == "screen_35"), "Bildschirm: Renamed")
        self.assertEqual(keys.action_labels()["screen_35"], "Bildschirm: Renamed")
        tab.config["L35"] = [{"kind": "text", "content": "High ID",
                              "x": 2, "y": 3, "font_size": 0}]
        gui.save_custom_screens(tab.config)
        self.assertEqual(gui.load_custom_screens(), tab.config)
        bindings = keys.default_bindings()
        bindings["2"]["L2"] = "screen_35"
        keys.save_bindings(bindings, self.bindings_file)
        with patch.object(gui.QMessageBox, "question", return_value=QMessageBox.No):
            tab.delete_screen()
        self.assertIn(35, keys.load_screens())
        with patch.object(gui.QMessageBox, "question", return_value=QMessageBox.Yes), \
                patch.object(gui, "save_custom_screens", side_effect=OSError("read only")), \
                patch.object(gui.QMessageBox, "critical") as error:
            tab.delete_screen()
            error.assert_called_once()
        self.assertIn(35, keys.load_screens())
        self.assertIn("L35", gui.load_custom_screens())
        self.assertEqual(tab.current_screen, "L35")
        keys.show_screen(35)
        with patch.object(gui.QMessageBox, "question", return_value=QMessageBox.Yes):
            tab.delete_screen()
        self.assertEqual(keys.read_screen(), 2)
        self.assertNotIn("L35", gui.load_custom_screens())
        self.assertEqual(keys.load_bindings(self.bindings_file)["2"]["L2"], "none")
        with patch.object(gui.QInputDialog, "getText", return_value=("Next", True)):
            tab.add_screen()
        self.assertEqual(tab.screen_number(), 36)
        self.assertEqual(gui.load_custom_screens()["L2"], before)
        tab.select_screen("L1")
        self.assertFalse(tab.add_btn.isEnabled())
        self.assertFalse(tab.rename_screen_btn.isEnabled())
        self.assertFalse(tab.delete_screen_btn.isEnabled())
        # The default-layout operation must leave additional layouts alone.
        with patch.object(gui.QMessageBox, "question", return_value=QMessageBox.Yes), \
                patch.object(gui.QMessageBox, "information"):
            tab.on_apply_default_layout()
        self.assertIn("L36", gui.load_custom_screens())
        tab.close()
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
