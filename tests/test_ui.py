"""Navigation, window sizing and scaled input tests without hardware writes."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PyQt5.QtCore import Qt, QPoint, QPointF, QEvent
from PyQt5.QtGui import QColor, QPixmap, QMouseEvent
from PyQt5.QtTest import QTest, QSignalSpy
from PyQt5.QtWidgets import QApplication

import g510_app as gui
import g510_canvas as keyboard
import g510_screen_keys as keys


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        pixmap = QPixmap(160, 43)
        pixmap.fill(QColor("#c0d796"))
        for context in (
            patch.dict(os.environ, XDG_RUNTIME_DIR=str(self.root)),
            patch.object(keys, "SCREENS_PATH", self.root / "screens.json"),
            patch.object(keys, "CLOCK_LAYOUT_PATH", self.root / "clock_layout"),
            patch.object(gui, "CUSTOM_SCREENS_FILE", self.root / "custom_screens.txt"),
            patch.object(gui, "load_custom_screens", return_value={
                "L2": [], "L3": [], "L4": [], "L5": []}),
            patch.object(gui, "render_preview", return_value=(pixmap, {}, None)),
            patch.object(gui.GameLogosTab, "showEvent", return_value=None),
        ):
            context.start()
            self.addCleanup(context.stop)

    def window(self):
        window = gui.MainWindow()
        window.show()
        self.app.processEvents()
        self.addCleanup(self.dispose_widget, window)
        return window

    def dispose_widget(self, widget):
        widget.close()
        self.app.processEvents()
        widget.deleteLater()
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)

    @staticmethod
    def preview_point(canvas, x, y):
        scale, left, top = canvas.preview_transform()
        return QPoint(round(left + x * gui.PREVIEW_SCALE * scale),
                      round(top + y * gui.PREVIEW_SCALE * scale))

    @staticmethod
    def move_drag(canvas, position):
        # Offscreen platforms do not reliably synthesize cursor motion.
        QApplication.sendEvent(canvas, QMouseEvent(
            QEvent.MouseMove, QPointF(position), Qt.NoButton, Qt.LeftButton, Qt.NoModifier))

    def test_navigation_keeps_pages_and_visibility_timers_in_sync(self):
        window = self.window()
        self.assertEqual(window.navigation.count(), 5)
        self.assertFalse(hasattr(window, "cooling_tab"))
        self.assertTrue(window.overview_tab.timer.isActive())
        self.assertFalse(window.custom_tab.preview_timer.isActive())
        self.assertFalse(window.keyboard_tab.lcd_mirror_timer.isActive())
        for index, page in enumerate(window.page_widgets):
            window.navigation.setCurrentRow(index)
            self.app.processEvents()
            self.assertIs(window.pages.currentWidget().widget(), page)
            self.assertEqual(window.page_title.text(), window.navigation.item(index).text())
            self.assertTrue(page.isVisible())
            self.assertEqual(window.overview_tab.timer.isActive(), index == 0)
            self.assertEqual(window.custom_tab.preview_timer.isActive(), index == 1)
            self.assertEqual(window.keyboard_tab.lcd_mirror_timer.isActive(), index == 3)
            self.assertTrue(window.save_all_btn.isVisible())
        window.navigation.setCurrentRow(0)
        window.overview_tab.navigate.emit(2)
        self.assertEqual(window.navigation.currentRow(), 2)

    def test_window_uses_large_sizes_and_small_pages_remain_scrollable(self):
        window = self.window()
        self.assertGreater(window.maximumWidth(), 10000)
        self.assertGreater(window.maximumHeight(), 10000)
        for width, height in ((1024, 700), (1440, 900), (1920, 1080), (2560, 1440)):
            window.resize(width, height)
            self.app.processEvents()
            self.assertEqual((window.width(), window.height()), (width, height))
            for index in range(5):
                window.navigation.setCurrentRow(index)
                self.app.processEvents()
                scroll = window.pages.currentWidget()
                self.assertTrue(scroll.geometry().contains(scroll.viewport().geometry()))
                if width >= 1440:
                    self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
                save_rect = window.save_all_btn.rect()
                self.assertTrue(window.rect().contains(
                    window.save_all_btn.mapTo(window, save_rect.bottomRight())))
                self.assertTrue(window.navigation.isVisible())
        window.navigation.setCurrentRow(1)
        large_width = window.custom_tab.preview_canvas.width()
        window.resize(1024, 700)
        self.app.processEvents()
        self.assertGreater(large_width, window.custom_tab.preview_canvas.width())

    def test_fullscreen_shortcuts_and_restore_maximized_state(self):
        window = self.window()
        window.resize(1200, 750)
        self.app.processEvents()
        QTest.keyClick(window, Qt.Key_F11)
        self.app.processEvents()
        self.assertTrue(window.isFullScreen())
        self.assertIn("verlassen", window.fullscreen_button.text())
        QTest.keyClick(window, Qt.Key_Escape)
        self.app.processEvents()
        self.assertFalse(window.isFullScreen())
        self.assertFalse(window.isMaximized())
        self.assertEqual((window.width(), window.height()), (1200, 750))
        window.showMaximized()
        self.app.processEvents()
        self.assertTrue(window.isMaximized())
        window.fullscreen_button.click()
        self.app.processEvents()
        self.assertTrue(window.isFullScreen())
        window.fullscreen_button.click()
        self.app.processEvents()
        self.assertTrue(window.isMaximized())
        self.assertFalse(window.isFullScreen())

    def test_preview_paint_and_drag_use_same_transform_at_all_sizes(self):
        canvas = gui.ScreenPreviewCanvas()
        self.addCleanup(self.dispose_widget, canvas)
        pixmap = QPixmap(160, 43)
        pixmap.fill(QColor("#c0d796"))
        canvas.show()
        for width, height in ((320, 240), (640, 172), (1280, 600)):
            canvas.resize(width, height)
            text = {"kind": "text", "content": "A", "x": 10, "y": 5}
            canvas.set_data(pixmap, [text])
            self.app.processEvents()
            image = canvas.grab().toImage()
            self.assertEqual(image.pixelColor(self.preview_point(canvas, 150, 30)),
                             QColor("#c0d796"))
            if height == 240:
                self.assertEqual(image.pixelColor(0, 0), QColor("#0b111b"))
            moved = QSignalSpy(canvas.element_moved)
            QTest.mousePress(canvas, Qt.LeftButton, pos=self.preview_point(canvas, 12, 7))
            self.move_drag(canvas, self.preview_point(canvas, 30, 15))
            QTest.mouseRelease(canvas, Qt.LeftButton, pos=self.preview_point(canvas, 30, 15))
            self.assertEqual((text["x"], text["y"]), (28, 13))
            self.assertEqual(list(moved)[-1], [0, 28, 13])
            QTest.mousePress(canvas, Qt.LeftButton, pos=QPoint(0, 0))
            self.assertIsNone(canvas._drag_index)

    def test_visualizer_and_history_resize_remain_in_lcd_pixels(self):
        canvas = gui.ScreenPreviewCanvas()
        self.addCleanup(self.dispose_widget, canvas)
        canvas.show()
        for width, height in ((480, 240), (1280, 600)):
            canvas.resize(width, height)
            for kind in ({"kind": "visualizer"},
                         {"kind": "sensor", "sensor": "NET_DOWN", "style": "history"}):
                element = {**kind, "x": 10, "y": 5, "width": 30, "height": 15}
                canvas.set_data(None, [element])
                self.app.processEvents()
                resized = QSignalSpy(canvas.element_resized)
                QTest.mousePress(canvas, Qt.LeftButton, pos=self.preview_point(canvas, 40, 20))
                self.move_drag(canvas, self.preview_point(canvas, 50, 25))
                QTest.mouseRelease(canvas, Qt.LeftButton, pos=self.preview_point(canvas, 50, 25))
                self.assertEqual((element["width"], element["height"]), (40, 20))
                self.assertEqual(list(resized)[-1], [0, 40])

    def test_network_history_style_is_editable_and_persists_dimensions(self):
        tab = gui.CustomScreensTab()
        self.addCleanup(self.dispose_widget, tab)
        index = tab.style_combo.findData("history")
        self.assertFalse(tab.style_combo.model().item(index).isEnabled())
        tab.sensor_combo.setCurrentIndex(tab.sensor_combo.findData("NET_DOWN"))
        self.assertTrue(tab.style_combo.model().item(index).isEnabled())
        tab.style_combo.setCurrentIndex(index)
        self.assertFalse(tab.font_size_combo.isEnabled())
        tab.on_add_element()
        el = tab.config["L2"][-1]
        self.assertEqual(el["style"], "history")
        el.update(x=100, y=5, width=48, height=12)
        el["max_width"] = 100
        gui.save_custom_screens(tab.config)
        content = gui.CUSTOM_SCREENS_FILE.read_text()
        self.assertIn("style=history", content)
        self.assertIn("height=12", content)
        self.assertIn("max_width=100", content)
        tab.sensor_combo.setCurrentIndex(tab.sensor_combo.findData("CPU_PCT"))
        self.assertEqual(tab.style_combo.currentData(), "number")
        self.assertTrue(tab.font_size_combo.isEnabled())

    def test_keyboard_gkeys_and_profiles_hit_test_after_scaling(self):
        canvas = keyboard.G510Canvas()
        self.addCleanup(self.dispose_widget, canvas)
        canvas.show()
        for width, height in ((480, 220), (1000, 450), (1600, 800)):
            canvas.resize(width, height)
            self.app.processEvents()
            gkeys, profiles = QSignalSpy(canvas.gkey_clicked), QSignalSpy(canvas.mkey_clicked)
            scale, left, top = canvas.canvas_transform()
            for cell in keyboard.ALL_CELLS:
                if cell.kind != "gkey" and cell.key_name not in ("_M1", "_M2", "_M3"):
                    continue
                center = canvas._cell_rect(cell).center()
                point = QPoint(round(left + center.x() * scale),
                               round(top + center.y() * scale))
                QTest.mouseClick(canvas, Qt.LeftButton, pos=point)
            self.assertEqual(len(gkeys), 18)
            self.assertEqual([row[0] for row in profiles], ["M1", "M2", "M3"])

    def test_system_editor_labels_limits_and_gauge_options(self):
        window = self.window()
        window.navigation.setCurrentRow(1)
        tab = window.custom_tab
        tab.config["L2"] = gui.build_layout_preset("system")
        tab.select_screen("L2")
        self.assertFalse(tab.fix_overflow_btn.isVisible())
        self.assertEqual(len(tab.preview_canvas._elements), 38)
        index = next(i for i, el in enumerate(tab.config["L2"])
                     if el.get("sensor") == "CPU_CORE_19")
        tab.on_element_label_edited(index, "")
        self.assertTrue(tab.config["L2"][index]["hide_label"])
        tab.on_element_label_edited(index, "T20")
        self.assertFalse(tab.config["L2"][index]["hide_label"])
        self.assertIn("label2=T20", gui.CUSTOM_SCREENS_FILE.read_text())
        tab.sensor_combo.setCurrentIndex(tab.sensor_combo.findData("RAM_PCT"))
        tab.style_combo.setCurrentIndex(tab.style_combo.findData("gauge"))
        self.assertFalse(tab.font_size_combo.isEnabled())
        self.assertFalse(tab.orientation_combo.isVisible())
        for _ in range(3):
            tab.on_add_element()
        with patch.object(gui.QMessageBox, "warning") as warning:
            tab.on_add_element()
        warning.assert_called_once()
        self.assertEqual(sum(el.get("kind") == "sensor" for el in tab.config["L2"]), 32)
        tab.sensor_combo.setCurrentIndex(tab.sensor_combo.findData("NET_UP"))
        self.assertEqual(tab.style_combo.currentData(), "number")
        tab.on_add_frame()
        tab.on_add_frame()
        with patch.object(gui.QMessageBox, "warning") as warning:
            tab.on_add_frame()
        warning.assert_called_once()
        self.assertEqual(sum(el.get("kind") == "frame" for el in tab.config["L2"]), 8)
        tab.select_screen("L1")
        self.assertFalse(tab.add_frame_btn.isEnabled())

    def test_all_20_compact_bars_have_individual_hit_and_resize_targets(self):
        canvas = gui.ScreenPreviewCanvas()
        self.addCleanup(self.dispose_widget, canvas)
        canvas.show()
        elements = gui.build_layout_preset("system")
        bounds = {}
        rank = 0
        for el in elements:
            if el["kind"] != "sensor":
                continue
            if el["sensor"].startswith("CPU_CORE_"):
                bounds[rank] = {
                    "bar_x1": el["x"], "bar_x2": el["x"] + el["width"],
                    "bar_y1": el["y"], "bar_y2": el["y"] + el["height"], "vertical": 1}
            rank += 1
        canvas.set_data(None, elements, bounds)
        for width, height in ((480, 240), (1280, 600)):
            canvas.resize(width, height)
            self.app.processEvents()
            for i, el in enumerate(elements):
                if not el.get("sensor", "").startswith("CPU_CORE_"):
                    continue
                body = canvas.preview_position(self.preview_point(canvas, el["x"] + 1, 25))
                self.assertEqual(canvas._element_at(body), i)
                handle = canvas._resize_handle_rect(i).center()
                self.assertEqual(canvas._resize_handle_at(handle), i)
                self.assertEqual(canvas._element_rect(i).width(), 3 * gui.PREVIEW_SCALE)

    def test_frame_and_gauge_resize_use_box_dimensions(self):
        canvas = gui.ScreenPreviewCanvas()
        self.addCleanup(self.dispose_widget, canvas)
        canvas.show()
        canvas.resize(1000, 450)
        for element in (
            {"kind": "frame", "x": 10, "y": 5, "width": 30, "height": 15},
            {"kind": "sensor", "sensor": "RAM_PCT", "style": "gauge",
             "x": 10, "y": 5, "width": 30, "height": 15},
        ):
            canvas.set_data(None, [element])
            QTest.mousePress(canvas, Qt.LeftButton, pos=self.preview_point(canvas, 40, 20))
            self.move_drag(canvas, self.preview_point(canvas, 50, 25))
            QTest.mouseRelease(canvas, Qt.LeftButton, pos=self.preview_point(canvas, 50, 25))
            self.assertEqual((element["width"], element["height"]), (40, 20))

    def test_clock_layout_selector_tracks_physical_keys_without_overwriting_selection(self):
        window = self.window()
        window.navigation.setCurrentRow(1)
        tab = window.custom_tab
        tab.select_screen("L1")
        self.assertTrue(tab.clock_layout_row.isVisible())
        self.assertEqual(tab.clock_layout_combo.count(), 20)
        self.assertEqual(tab.clock_layout_combo.currentData(), 0)
        tab.cycle_clock_layout(-1)
        self.assertEqual(keys.load_clock_layout(), 19)
        self.assertEqual(tab.clock_layout_combo.currentData(), 19)
        tab.cycle_clock_layout(1)
        self.assertEqual(keys.load_clock_layout(), 0)
        tab.clock_layout_combo.setCurrentIndex(12)
        tab.on_clock_layout_selected()
        self.assertEqual(keys.load_clock_layout(), 12)
        keys.save_clock_layout(7)
        with patch.object(gui, "save_clock_layout") as save:
            tab.refresh_preview()
        save.assert_not_called()
        self.assertEqual(tab.clock_layout_combo.currentData(), 7)
        self.assertIn("Uhr-Layout zurück", tab.function_buttons["L2"].text())
        self.assertIn("Uhr-Layout weiter", tab.function_buttons["L3"].text())
        tab.select_screen("L2")
        self.assertFalse(tab.clock_layout_row.isVisible())
        self.assertEqual(keys.load_clock_layout(), 7)

    def test_clock_layout_io_errors_are_visible_and_never_saved_as_default(self):
        tab = self.window().custom_tab
        tab.select_screen("L1")
        keys.CLOCK_LAYOUT_PATH.write_text("broken")
        with patch.object(gui, "save_clock_layout") as save:
            tab.refresh_preview()
        save.assert_not_called()
        self.assertIn("konnte nicht geladen", tab.drag_hint.text())
        self.assertIsNone(tab.preview_canvas._pixmap)
        with patch.object(gui.QMessageBox, "critical") as message:
            tab.cycle_clock_layout(1)
        message.assert_called_once()
        self.assertEqual(keys.CLOCK_LAYOUT_PATH.read_text(), "broken")
        tab.clock_layout_combo.setCurrentIndex(3)
        tab.on_clock_layout_selected()
        self.assertEqual(keys.load_clock_layout(), 3)
        self.assertNotIn("konnte nicht geladen", tab.drag_hint.text())
        with patch.object(gui, "save_clock_layout", side_effect=PermissionError("Testzugriff verweigert")), \
                patch.object(gui.QMessageBox, "critical") as message:
            tab.clock_layout_combo.setCurrentIndex(12)
            tab.on_clock_layout_selected()
        message.assert_called_once()
        self.assertEqual(keys.load_clock_layout(), 3)
        self.assertEqual(tab.clock_layout_combo.currentData(), 3)

    def test_clock_controls_fit_large_windows_without_horizontal_scrolling(self):
        window = self.window()
        window.navigation.setCurrentRow(1)
        window.custom_tab.select_screen("L1")
        for width, height in ((1440, 900), (1920, 1200)):
            window.resize(width, height)
            self.app.processEvents()
            scroll = window.pages.currentWidget()
            self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
            self.assertTrue(window.custom_tab.clock_layout_combo.isVisible())

    def test_invalid_bindings_keep_key_panel_disabled_without_crashing(self):
        with patch("g510_key_settings.load_bindings", side_effect=ValueError("Testbelegung defekt")):
            window = self.window()
        self.assertIn("Testbelegung defekt", window.keys_tab.status.text())
        self.assertTrue(all(not combo.isEnabled() for combo in window.keys_tab.combos.values()))

    def test_bars_and_image_handles_use_scaled_input(self):
        canvas = gui.ScreenPreviewCanvas()
        self.addCleanup(self.dispose_widget, canvas)
        canvas.show()
        for width, height in ((480, 240), (1280, 600)):
            canvas.resize(width, height)
            for vertical in (False, True):
                element = {"sensor": "CPU_PCT", "style": "bar", "x": 10, "y": 5,
                           "width": 40, "height": 20,
                           "orientation": "vertical" if vertical else "horizontal"}
                bound = {"bar_x1": 10, "bar_x2": 50, "bar_y1": 5, "bar_y2": 25,
                         "vertical": int(vertical)}
                canvas.set_data(None, [element], {0: bound})
                self.app.processEvents()
                handle = canvas._resize_handle_rect(0).center()
                scale, left, top = canvas.preview_transform()
                start = QPoint(round(left + handle.x() * scale),
                               round(top + handle.y() * scale))
                end = start + QPoint(0 if vertical else round(10 * 4 * scale),
                                     round(5 * 4 * scale) if vertical else 0)
                QTest.mousePress(canvas, Qt.LeftButton, pos=start)
                self.move_drag(canvas, end)
                QTest.mouseRelease(canvas, Qt.LeftButton, pos=end)
                self.assertEqual(element["height"] if vertical else element["width"],
                                 25 if vertical else 50)
            image = {"kind": "image", "src": "original.png", "x": 10, "y": 5,
                     "width": 30, "height": 15}
            canvas.set_data(None, [image])
            requested = QSignalSpy(canvas.image_resize_requested)
            QTest.mousePress(canvas, Qt.LeftButton, pos=self.preview_point(canvas, 40, 20))
            self.move_drag(canvas, self.preview_point(canvas, 50, 25))
            QTest.mouseRelease(canvas, Qt.LeftButton, pos=self.preview_point(canvas, 50, 25))
            self.assertEqual(list(requested)[-1], [0, 40, 20])
            self.assertEqual((image["width"], image["height"]), (30, 15))

    def test_overview_reports_failures_and_clears_old_preview(self):
        overview = gui.OverviewTab()
        self.addCleanup(self.dispose_widget, overview)
        overview.refresh()
        self.assertEqual(overview.screen_name.text(), "System")
        self.assertEqual(overview.screen_count.text(), "5")
        with patch.object(gui, "render_preview", return_value=(None, {}, "Renderer fehlt")):
            overview.refresh()
        self.assertEqual(overview.error.text(), "Renderer fehlt")
        self.assertIsNone(overview.preview._pixmap)
        with patch.object(gui, "load_screens", side_effect=ValueError("Katalog defekt")):
            overview.refresh()
        self.assertIn("Katalog defekt", overview.error.text())
        self.assertEqual(overview.screen_name.text(), "Nicht verfügbar")


if __name__ == "__main__":
    unittest.main()
