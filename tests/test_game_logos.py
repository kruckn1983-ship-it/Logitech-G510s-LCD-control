"""Game-logo import, preview refresh and failure regressions without Steam."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PyQt5.QtCore import QEvent, QProcess
from PyQt5.QtGui import QColor, QImage
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

import g510_app as gui
from PIL import Image, ImageDraw
from native_support import compile_renderer_fixture


class GameLogoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.native_tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.native_tmp.cleanup)
        source = Path(cls.native_tmp.name) / "logo.c"
        source.write_text(
            '#define main lcd_main\n'
            f'#include "{gui.PROJECT_DIR}/src/g510_lcd_stats.c"\n'
            '#undef main\n'
            'int main(int argc,char **argv) {int w=0,h=0;'
            'if(!convert_game_artwork(argv[1],NULL,argv[2],&w,&h))return 1;'
            'printf("%d %d\\n",w,h);return 0;}\n')
        cls.native = source.with_suffix("")
        compile_renderer_fixture(source, cls.native)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        context = patch.object(gui, "DATA_DIR", self.root)
        context.start()
        self.addCleanup(context.stop)
        self.tab = gui.GameLogosTab()
        self.addCleanup(self.dispose)
        self.tab.games = {7670: "BioShock", 409710: "BioShock Remastered"}
        self.tab.libs = []
        self.tab.fill_list()
        self.tab.list.setCurrentRow(0)
        self.input = self.root / "logo.png"
        image = QImage(597, 215, QImage.Format_RGB32)
        image.fill(QColor("white"))
        for y in range(35, 180):
            for x in range(80, 520):
                image.setPixelColor(x, y, QColor("black"))
        self.assertTrue(image.save(str(self.input)))

    def dispose(self):
        self.tab.close()
        self.app.processEvents()
        self.tab.deleteLater()
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)

    def choose(self, source=None):
        with patch.object(gui.QFileDialog, "getOpenFileName",
                          return_value=(str(source or self.input), "")):
            self.tab.choose_logo()

    def files(self):
        paths = [
            self.tab.custom_dir / "7670.png",
            self.tab.logo_dir / "7670.bin",
            self.tab.logo_dir / "7670.size",
        ]
        return [p.read_bytes() if p.exists() else None for p in paths]

    def test_import_is_immediately_visible_and_keeps_selected_game(self):
        self.assertIsNone(self.tab.preview.pixmap())
        self.choose()
        self.assertEqual(self.tab.current_appid(), 7670)
        self.assertEqual(self.tab.preview.text(), "")
        self.assertEqual(self.tab.preview.pixmap().size().width(), 640)
        self.assertEqual(self.tab.preview.pixmap().size().height(), 172)
        self.assertIn("Import erfolgreich", self.tab.source_label.text())
        self.assertIn("*", self.tab.list.currentItem().text())
        self.assertTrue(self.tab.reset_btn.isEnabled())
        self.assertTrue(all(self.files()))
        self.assertEqual(list(self.tab.custom_dir.glob(".import-*")), [])
        self.assertEqual(list(self.tab.logo_dir.glob(".logo-*")), [])

    def test_replacement_refreshes_old_pixmap_not_only_the_file(self):
        self.choose()
        old = self.tab.preview.pixmap().toImage()
        white = QImage(597, 215, QImage.Format_RGB32)
        white.fill(QColor("white"))
        self.assertTrue(white.save(str(self.input)))
        self.choose()
        new = self.tab.preview.pixmap().toImage()
        self.assertNotEqual(old, new)
        self.assertEqual(self.tab.current_appid(), 7670)

    def test_qt_png_import_keeps_opaque_logo_polarity_and_pixels(self):
        image = Image.new("RGB", (597, 215), "white")
        ImageDraw.Draw(image).rectangle((80, 35, 520, 180), fill="black")
        image.save(self.input)
        expected = self.root / "direct.bin"
        result = subprocess.run(
            [sys.executable, str(gui.PROJECT_DIR / "src/png-to-lcd.py"),
             str(self.input), str(expected), "160", "43", "--lcd-logo"],
            check=True, capture_output=True, text=True)
        self.choose()
        self.assertEqual((self.tab.logo_dir / "7670.bin").read_bytes(), expected.read_bytes())
        self.assertEqual((self.tab.logo_dir / "7670.size").read_text(), result.stdout)

    def test_opaque_rgba_and_palette_alpha_match_rgb_but_transparency_is_preserved(self):
        image = Image.new("RGB", (80, 30), "white")
        ImageDraw.Draw(image).rectangle((10, 10, 60, 20), fill="black")
        expected = None
        for mode in ("RGB", "RGBA", "P"):
            source = self.root / f"{mode}.png"
            converted = image.convert(mode)
            if mode == "P":
                converted.info["transparency"] = bytes([255] * 256)
            converted.save(source)
            output = source.with_suffix(".bin")
            subprocess.run(
                [sys.executable, str(gui.PROJECT_DIR / "src/png-to-lcd.py"),
                 str(source), str(output), "160", "43", "--upscale", "--invert-dark"],
                check=True, capture_output=True)
            if expected is None:
                expected = output.read_bytes()
            self.assertEqual(output.read_bytes(), expected, mode)
        transparent = Image.new("RGBA", (80, 30), (255, 255, 255, 0))
        ImageDraw.Draw(transparent).rectangle((10, 10, 60, 20), fill="white")
        transparent.save(self.input)
        self.choose()
        self.tab.optimize_logo.setChecked(False)
        self.assertEqual((self.tab.logo_dir / "7670.bin").read_bytes(), expected)

    def test_new_import_optimized_by_default_and_switch_preserves_original(self):
        self.choose()
        marker = self.tab.custom_dir / "7670.optimized"
        self.assertTrue(marker.is_file())
        self.assertTrue(self.tab.optimize_logo.isChecked())
        original = (self.tab.custom_dir / "7670.png").read_bytes()
        optimized = (self.tab.logo_dir / "7670.bin").read_bytes()
        self.tab.optimize_logo.setChecked(False)
        self.assertFalse(marker.exists())
        self.assertEqual((self.tab.custom_dir / "7670.png").read_bytes(), original)
        self.assertNotEqual((self.tab.logo_dir / "7670.bin").read_bytes(), optimized)
        self.tab.optimize_logo.setChecked(True)
        self.assertEqual((self.tab.logo_dir / "7670.bin").read_bytes(), optimized)
        self.assertEqual((self.tab.custom_dir / "7670.png").read_bytes(), original)

    def test_existing_import_is_not_optimized_on_selection(self):
        self.tab.custom_dir.mkdir(parents=True)
        target = self.tab.custom_dir / "7670.png"
        target.write_bytes(self.input.read_bytes())
        self.tab.convert(7670, target)
        before = self.files()
        self.tab.update_detail()
        self.assertFalse(self.tab.optimize_logo.isChecked())
        self.assertTrue(self.tab.optimize_logo.isEnabled())
        self.assertEqual(self.files(), before)
        self.assertFalse((self.tab.custom_dir / "7670.optimized").exists())

    def test_failed_optimization_switch_restores_setting(self):
        self.choose()
        before = self.files()
        with patch.object(self.tab, "convert", side_effect=ValueError("fixture error")), \
                patch.object(gui.QMessageBox, "warning") as warning:
            self.tab.optimize_logo.setChecked(False)
        warning.assert_called_once()
        self.assertTrue(self.tab.optimize_logo.isChecked())
        self.assertTrue((self.tab.custom_dir / "7670.optimized").exists())
        self.assertEqual(self.files(), before)

    def test_optimization_uses_available_width_and_removes_empty_margins(self):
        self.choose()
        width, height = map(int, (self.tab.logo_dir / "7670.size").read_text().split())
        self.assertEqual(width, 130)
        self.assertEqual(height, 43)
        self.assertLessEqual(width, 160)
        self.assertEqual(len((self.tab.logo_dir / "7670.bin").read_bytes()),
                         ((width + 7) // 8) * height)

    def test_native_converter_and_pregeneration_follow_saved_mode(self):
        self.choose()
        for enabled in (True, False):
            with self.subTest(optimized=enabled):
                self.tab.optimize_logo.setChecked(enabled)
                expected = (self.tab.logo_dir / "7670.bin").read_bytes()
                source = self.tab.custom_dir / "7670.png"
                native = self.root / "native.bin"
                result = subprocess.run([str(self.native), str(source), str(native)],
                                        check=True, capture_output=True, text=True)
                self.assertEqual(native.read_bytes(), expected)
                self.assertEqual(result.stdout, (self.tab.logo_dir / "7670.size").read_text())
                home = self.root / "home"
                custom = home / ".local/share/g510-lcd/custom_logos"
                custom.mkdir(parents=True, exist_ok=True)
                (custom / "7670.png").write_bytes(source.read_bytes())
                marker = custom / "7670.optimized"
                if enabled:
                    marker.write_text("1\n")
                else:
                    marker.unlink(missing_ok=True)
                output = self.root / "pregenerated"
                with patch.dict(os.environ, HOME=str(home)), \
                        patch.object(self.tab.steam, "OUT_DIR", str(output)), \
                        patch.object(self.tab.steam, "libraries", return_value=[]), \
                        patch.object(self.tab.steam, "games", return_value={7670: "BioShock"}), \
                        patch.object(self.tab.steam, "find_artwork", return_value=None), \
                        patch.object(sys, "argv", ["pregenerate-game-logos.py", "--force"]):
                    self.tab.steam.main()
                self.assertEqual((output / "7670.bin").read_bytes(), expected)

    def test_optimizer_handles_padding_dark_background_transparency_and_shapes(self):
        for width, height in ((240, 80), (20, 180), (800, 25)):
            expected = None
            for mode in ("light", "dark", "transparent"):
                with self.subTest(shape=(width, height), background=mode):
                    background = {"light": "white", "dark": "black",
                                  "transparent": (0, 0, 0, 0)}[mode]
                    ink = "black" if mode == "light" else "white"
                    image = Image.new("RGBA", (width + 100, height + 100), background)
                    draw = ImageDraw.Draw(image)
                    draw.rectangle((50, 50, 50 + width - 1, 50 + height - 1), fill=ink)
                    # A gap through the mark must survive the threshold.
                    draw.rectangle((50 + width // 3, 50, 50 + 2 * width // 3,
                                    50 + height - 1), fill=background)
                    source = self.root / "shape.png"
                    output = self.root / "shape.bin"
                    image.save(source)
                    result = subprocess.run(
                        [sys.executable, str(gui.PROJECT_DIR / "src/png-to-lcd.py"),
                         str(source), str(output), "160", "43", "--lcd-logo"],
                        check=True, capture_output=True, text=True)
                    w, h = map(int, result.stdout.split())
                    self.assertTrue(0 < w <= 160 and 0 < h <= 43)
                    self.assertTrue(w == 160 or h == 43)
                    bits = output.read_bytes()
                    self.assertEqual(len(bits), ((w + 7) // 8) * h)
                    ink_count = sum((bits[y * ((w + 7) // 8) + x // 8] >> (x % 8)) & 1
                                    for y in range(h) for x in range(w))
                    self.assertGreater(ink_count, w * h // 3)
                    self.assertLess(ink_count, w * h * 9 // 10)
                    if expected is None:
                        expected = result.stdout, bits
                    self.assertEqual((result.stdout, bits), expected)

    def test_command_line_import_enables_optimization_and_remove_cleans_mode(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "add_game_logo", gui.PROJECT_DIR / "scripts/add-game-logo.py")
        script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(script)
        with patch.object(script, "BASE", str(self.root)), \
                patch.object(sys, "argv", ["add-game-logo.py", "7670", str(self.input)]):
            self.assertEqual(script.main(), 0)
        self.assertTrue((self.root / "custom_logos/7670.png").is_file())
        self.assertTrue((self.root / "custom_logos/7670.optimized").is_file())
        with patch.object(script, "BASE", str(self.root)), \
                patch.object(sys, "argv", ["add-game-logo.py", "7670", "--remove"]):
            self.assertEqual(script.main(), 0)
        self.assertFalse((self.root / "custom_logos/7670.png").exists())
        self.assertFalse((self.root / "custom_logos/7670.optimized").exists())

    def test_failed_conversion_preserves_previous_source_cache_and_preview(self):
        self.choose()
        before = self.files()
        old = self.tab.preview.pixmap().toImage()
        result = subprocess.CompletedProcess([], 1, "", "converter fixture failure")
        with patch.object(gui.subprocess, "run", return_value=result), \
                patch.object(gui.QMessageBox, "warning") as warning:
            self.choose()
        warning.assert_called_once()
        self.assertIn("converter fixture failure", warning.call_args.args[2])
        self.assertEqual(self.files(), before)
        self.assertEqual(self.tab.preview.pixmap().toImage(), old)

    def test_invalid_image_and_failed_png_save_report_errors_without_importing(self):
        self.input.write_text("not an image")
        with patch.object(gui.QMessageBox, "warning") as warning:
            self.choose()
        warning.assert_called_once()
        self.assertEqual(self.files(), [None, None, None])
        image = QImage(10, 10, QImage.Format_RGB32)
        image.fill(QColor("black"))
        image.save(str(self.input))
        with patch.object(gui.QImage, "save", return_value=False), \
                patch.object(gui.QMessageBox, "warning") as warning:
            self.choose()
        warning.assert_called_once()
        self.assertEqual(self.files(), [None, None, None])

    def test_corrupt_converter_dimensions_or_bitmap_do_not_replace_cache(self):
        self.choose()
        before = self.files()
        for stdout, contents in (("garbage", b"abc"), ("161 43", b"abc"),
                                 ("1 1", b""), ("1 1 extra", b"a")):
            with self.subTest(dimensions=stdout):
                def corrupt(cmd, **kwargs):
                    Path(cmd[3]).write_bytes(contents)
                    return subprocess.CompletedProcess(cmd, 0, stdout, "")
                with patch.object(gui.subprocess, "run", side_effect=corrupt), \
                        patch.object(gui.QMessageBox, "warning") as warning:
                    self.choose()
                warning.assert_called_once()
                self.assertEqual(self.files(), before)

    def test_conversion_timeout_is_visible_and_preserves_files(self):
        self.choose()
        before = self.files()
        with patch.object(gui.subprocess, "run",
                          side_effect=subprocess.TimeoutExpired("converter", 30)), \
                patch.object(gui.QMessageBox, "warning") as warning:
            self.choose()
        warning.assert_called_once()
        self.assertEqual(self.files(), before)

    def test_cancel_does_not_change_logo(self):
        self.choose()
        before = self.files()
        with patch.object(gui.QFileDialog, "getOpenFileName", return_value=("", "")), \
                patch.object(self.tab, "convert") as convert:
            self.tab.choose_logo()
        convert.assert_not_called()
        self.assertEqual(self.files(), before)

    def test_background_generation_updates_selected_preview_after_finishing(self):
        self.tab.logo_dir.mkdir(parents=True)
        script = self.root / "generate.py"
        script.write_text(
            f"from pathlib import Path\nroot=Path({str(self.tab.logo_dir)!r})\n"
            "(root/'7670.size').write_text('8 1\\n')\n"
            "(root/'7670.bin').write_bytes(b'\\xff')\n")
        self.tab.logo_generator.start(sys.executable, [str(script)])
        for _ in range(100):
            QTest.qWait(10)
            if self.tab.logo_generator.state() == QProcess.NotRunning:
                break
        self.assertEqual(self.tab.logo_generator.state(), QProcess.NotRunning)
        self.assertEqual(self.tab.preview.text(), "")
        self.assertIsNotNone(self.tab.preview.pixmap())
        self.assertEqual(self.tab.current_appid(), 7670)

    def test_reset_regenerates_title_when_no_artwork_is_available(self):
        self.choose()
        with patch.object(self.tab.steam, "find_artwork", return_value=None), \
                patch.object(gui.QMessageBox, "warning") as warning:
            self.tab.reset_logo()
        warning.assert_not_called()
        self.assertFalse((self.tab.custom_dir / "7670.png").exists())
        self.assertFalse(self.tab.reset_btn.isEnabled())
        self.assertIsNotNone(self.tab.preview.pixmap())

    def test_invalid_cached_size_does_not_try_to_paint_outside_display(self):
        self.tab.logo_dir.mkdir(parents=True)
        (self.tab.logo_dir / "7670.size").write_text("999 999\n")
        (self.tab.logo_dir / "7670.bin").write_bytes(b"a")
        self.assertIsNone(self.tab.render_bin(7670))
