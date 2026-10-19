"""The extracted layout model and persistence remain independent from Qt."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import g510_layouts as layouts
import g510_layout_store as store


class LayoutModuleTests(unittest.TestCase):
    def test_import_has_no_qt_or_user_data_side_effects(self):
        with tempfile.TemporaryDirectory() as home:
            result = subprocess.run(
                [sys.executable, "-c",
                 "import sys; import g510_layouts, g510_layout_store;"
                 "assert not any(n.startswith('PyQt5') for n in sys.modules)"],
                env=dict(os.environ, HOME=home, PYTHONPATH=str(ROOT / "src")),
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(list(Path(home).iterdir()), [])

    def test_editor_limits_match_the_native_renderer(self):
        native = (ROOT / "src/g510_lcd_stats.c").read_text()
        for name, value in {
            "CPU_CORE_SENSOR_COUNT": layouts.CPU_CORE_SENSOR_COUNT,
            "MAX_ELEMENTS": layouts.MAX_SENSOR_ELEMENTS,
            "MAX_IMAGES": layouts.MAX_IMAGES_PER_SCREEN,
            "MAX_TEXTS": layouts.MAX_TEXTS_PER_SCREEN,
            "MAX_VISUALIZERS": layouts.MAX_VISUALIZERS_PER_SCREEN,
        }.items():
            with self.subTest(constant=name):
                match = re.search(rf"^#define {name} (\d+)\b", native, re.MULTILINE)
                self.assertIsNotNone(match)
                self.assertEqual(int(match[1]), value)
        self.assertEqual(layouts.GAME_BOUNDS_BASE, layouts.MAX_SENSOR_ELEMENTS)
        self.assertEqual(len(layouts.SENSOR_LABELS), len(layouts.SENSOR_CHOICES))

    def test_all_presets_round_trip_through_path_injected_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "layouts.txt"
            for preset in layouts.PRESET_NAMES:
                with self.subTest(preset=preset):
                    elements = layouts.build_layout_preset(preset)
                    store.save_custom_screens({"L2": elements, "L400": []}, path)
                    loaded = store.load_custom_screens(path, {1: "Uhr", 2: "System", 400: "Eigener"})
                    self.assertEqual(len(loaded["L2"]), len(elements))
                    self.assertEqual(loaded["L400"], [])
                    self.assertNotIn("L1", loaded)
                    store.save_custom_screens(loaded, path)
                    first = path.read_bytes()
                    store.save_custom_screens(store.load_custom_screens(path, {2: "System"}), path)
                    self.assertEqual(path.read_bytes(), first)

    def test_preset_results_do_not_share_mutable_elements(self):
        first = layouts.build_layout_preset("system")
        second = layouts.build_layout_preset("system")
        first[0]["x"] = 99
        self.assertEqual(second[0]["x"], 0)
