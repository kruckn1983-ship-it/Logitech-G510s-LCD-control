"""Twenty-thread sampling and the compact, editable system dashboard."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from native_support import compile_renderer_fixture
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import g510_app as gui


class SystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.directory = Path(cls.tmp.name)
        source = cls.directory / "system.c"
        source.write_text(
            '#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n'
            'static FILE *fixture_fopen(const char *,const char *);\n'
            '#define fopen fixture_fopen\n#define main lcd_main\n'
            f'#include "{ROOT / "src/g510_lcd_stats.c"}"\n'
            '#undef fopen\n#undef main\n'
            'static FILE *fixture_fopen(const char *p,const char *m) {\n'
            ' if (!strcmp(p,"/proc/stat")) p=getenv("STAT_FILE");\n'
            ' return fopen(p,m);\n}\n'
            'int main(void) {\n'
            ' if (getenv("TEST_FORMAT")) {\n'
            '  g_net_rate_valid=1;g_net_down_kbps=atof(getenv("RATE"));\n'
            '  char value[32];double pct;\n'
            '  get_sensor_value("NET_DOWN","compact",&pct,value,sizeof(value));\n'
            '  printf("%s\\n%d\\n",value,measure_builtin_label_width("DN",0)+2+\n'
            '   measure_builtin_text_width(value,0));return 0;\n'
            ' }\n'
            ' if (getenv("DRAW_GAUGE")) {\n'
            '  cpu_core_valid[0]=1;cpu_core_percent[0]=atof(getenv("RATE"));\n'
            '  element_t el={.sensor="CPU_CORE_0",.style="gauge",.x=10,.y=10,.width=49,.height=7};\n'
            '  g15canvas c G15_CANVAS_AUTO={0};g15r_initCanvas(&c);draw_element(&c,&el);\n'
            '  write_ppm(&c,getenv("OUTPUT"));return 0;\n'
            ' }\n'
            ' if (getenv("DRAW_SYSTEM")) {\n'
            '  for (int i=0;i<20;i++) {cpu_core_valid[i]=1;cpu_core_percent[i]=(i+1)*5;}\n'
            '  g_nvidia_gpu_temp_c=37; g_nvidia_gpu_percent=65;\n'
            '  g_nvidia_vram_used=3; g_nvidia_vram_total=10;\n'
            '  g_net_rate_valid=!getenv("NO_NETWORK");\n'
            '  g_net_up_kbps=atof(getenv("RATE")); g_net_down_kbps=g_net_up_kbps;\n'
            '  g15canvas c G15_CANVAS_AUTO={0};g15r_initCanvas(&c);\n'
            '  draw_custom_screen(&c,2);write_ppm(&c,getenv("OUTPUT"));\n'
            '  write_bounds_meta(getenv("OUTPUT"));\n'
            '  printf("%d %d %d %d\\n",current_custom_screen.count,\n'
            '   current_custom_screen.frame_count,current_custom_screen.text_count,\n'
            '   measure_builtin_text_width("23:59:59",0));\n'
            '  for (int i=0;i<g_element_bounds_count;i++) {\n'
            '   element_bounds_t *b=&g_element_bounds[i];\n'
            '   printf("%s %d %d %d %d %d %d\\n",current_custom_screen.elements[i].sensor,\n'
            '    b->label_x1,b->label_y1,b->value_x2,b->bar_x1,b->bar_x2,b->bar_y2);\n'
            '  }return 0;\n'
            ' }\n'
            ' int command;\n'
            ' while ((command=getchar())!=EOF) {\n'
            '  if (command==\'u\') update_cpu_core_percent();\n'
            '  for (int i=0;i<20;i++) {\n'
            '   char key[24],value[32];double pct;\n'
            '   snprintf(key,sizeof(key),"CPU_CORE_%d",i);\n'
            '   if (!find_sensor(key)) return 8;\n'
            '   get_sensor_value(key,"",&pct,value,sizeof(value));\n'
            '   printf("%s%s",i?"|":"",value);\n'
            '  } puts("");fflush(stdout);\n'
            ' }return 0;\n}\n')
        compile_renderer_fixture(source, cls.directory / "system")

    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        self.root = Path(self.home.name)
        self.stat = self.root / "stat"
        self.layout = self.root / ".local/share/g510-lcd/custom_screens.txt"
        self.layout.parent.mkdir(parents=True)
        self.env = dict(os.environ, HOME=str(self.root), STAT_FILE=str(self.stat),
                        XDG_RUNTIME_DIR=str(self.root), RATE="0",
                        OUTPUT=str(self.root / "system.ppm"))

    def counters(self, base, *, missing=None, percentages=None):
        percentages = percentages or list(range(5, 101, 5))
        self.stat.write_text("cpu  1 0 0 1 0 0 0 0\n" + "".join(
            f"cpu{i} {base * percentages[i]} 0 0 {base * (100-percentages[i])} 0 0 0 0\n"
            for i in range(20) if i != missing))

    def start_sampler(self):
        process = subprocess.Popen(
            [str(self.directory / "system")], env=self.env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        def stop():
            process.stdin.close()
            process.wait(timeout=5)
            process.stdout.close()
        self.addCleanup(stop)
        return process

    def sample(self, process, command="u"):
        process.stdin.write(command)
        process.stdin.flush()
        return process.stdout.readline().strip().split("|")

    def test_all_20_threads_have_independent_cached_values(self):
        self.counters(1)
        process = self.start_sampler()
        self.assertEqual(self.sample(process), ["N/V"] * 20)
        self.counters(2)
        expected = [f"{i}%" for i in range(5, 101, 5)]
        self.assertEqual(self.sample(process), expected)
        for _ in range(3):
            self.assertEqual(self.sample(process, "r"), expected)
        self.counters(3, percentages=[100] * 20)
        values = self.sample(process)
        self.assertEqual(len(values), 20)
        self.assertEqual(values[-1], "100%")
        self.assertNotEqual(values, expected)

    def test_counter_reset_offline_thread_and_reappearance(self):
        self.counters(10)
        process = self.start_sampler()
        self.sample(process)
        self.counters(11)
        self.sample(process)
        self.counters(1, missing=19)
        self.assertEqual(self.sample(process), ["N/V"] * 20)
        self.counters(2)
        self.assertEqual(self.sample(process)[19], "N/V")
        self.counters(3)
        self.assertEqual(self.sample(process)[19], "100%")
        self.counters(3)
        self.assertEqual(self.sample(process), ["N/V"] * 20)

    def save_preset(self):
        with patch.object(gui, "CUSTOM_SCREENS_FILE", self.layout):
            gui.save_custom_screens({"L2": gui.build_layout_preset("system")})

    def test_preset_roundtrip_preserves_20_threads_frames_and_gauge(self):
        self.save_preset()
        with patch.object(gui, "CUSTOM_SCREENS_FILE", self.layout):
            loaded = gui.load_custom_screens()["L2"]
            gui.save_custom_screens({"L2": loaded})
            self.assertEqual(gui.load_custom_screens()["L2"], loaded)
        bars = [el for el in loaded if el.get("sensor", "").startswith("CPU_CORE_")]
        self.assertEqual([el["sensor"] for el in bars], [f"CPU_CORE_{i}" for i in range(20)])
        self.assertTrue(all(el["hide_label"] and el["width"] == 3 for el in bars))
        self.assertEqual(sum(el["kind"] == "frame" for el in loaded), 6)
        self.assertEqual(sum(el.get("style") == "gauge" for el in loaded), 1)
        self.assertLessEqual(sum(el["kind"] == "sensor" for el in loaded), gui.MAX_SENSOR_ELEMENTS)
        self.assertTrue(all(f"CPU_CORE_{i}" in gui.BAR_CAPABLE_SENSORS for i in range(20)))

    def render(self, rate=0, **extra):
        result = subprocess.run([str(self.directory / "system")],
                                env=dict(self.env, DRAW_SYSTEM="1", RATE=str(rate), **extra),
                                capture_output=True, text=True, check=True)
        lines = result.stdout.splitlines()
        header = list(map(int, lines[0].split()))
        bounds = [(row.split()[0], list(map(int, row.split()[1:]))) for row in lines[1:]]
        return header, bounds

    def test_rendered_system_preserves_all_bars_and_column_boundaries(self):
        from PIL import Image
        self.save_preset()
        for rate in (0, 11, 14.3 * 1024, 10 * 1024 * 1024):
            header, bounds = self.render(rate)
            self.assertEqual(header[:3], [29, 6, 3])
            self.assertLessEqual(header[3], 34)
            for key, (x, y, end, bar_x1, bar_x2, bar_y2) in bounds:
                if key.startswith("CPU_CORE_"):
                    i = int(key[9:])
                    self.assertEqual((x, y, bar_x1, bar_x2, bar_y2),
                                     (2 + 4 * i, 11, 2 + 4 * i, 5 + 4 * i, 41))
                elif key in ("GPU_PCT", "VRAM_PCT") or (key == "GPU_EDGE_TEMP" and y == 21):
                    self.assertLessEqual(end, 103)
                    self.assertEqual(bar_y2, 41)
                elif key == "GPU_EDGE_TEMP":
                    self.assertLessEqual(end, 103)
                elif key == "CPU_TEMP":
                    self.assertLessEqual(end, 80)
                else:
                    self.assertLessEqual(end, 158)
            with Image.open(self.root / "system.ppm") as image:
                self.assertEqual(image.size, (160, 43))
                for i in range(20):
                    x = 2 + i * 4
                    self.assertTrue(all(image.getpixel((x, y)) == (20, 40, 15) for y in range(11, 41)))
                    if i < 19:
                        self.assertTrue(all(image.getpixel((x+3, y)) != (20, 40, 15) for y in range(11, 41)))
                    self.assertEqual(image.getpixel((x+1, 39)), (20, 40, 15))
                self.assertTrue(all(image.getpixel((81, y)) == (20, 40, 15) for y in range(43)))
                self.assertTrue(all(image.getpixel((105, y)) == (20, 40, 15) for y in range(43)))
        self.render(NO_NETWORK="1")

    def test_compact_rates_keep_full_units_inside_network_column(self):
        for rate, expected in ((0, "0B/s"), (0.5, "512B/s"), (11, "11.0KiB/s"),
                               (14.3 * 1024, "14.3MiB/s"), (999.9, "999.9KiB/s"),
                               (1023.9, "1024KiB/s"), (10 * 1024 * 1024, "10.0GiB/s")):
            result = subprocess.run(
                [str(self.directory / "system")],
                env=dict(self.env, TEST_FORMAT="1", RATE=str(rate)),
                capture_output=True, text=True, check=True)
            value, width = result.stdout.splitlines()
            self.assertEqual(value, expected)
            self.assertLessEqual(int(width), 50)

    def test_gauge_fill_and_text_stay_inside_49_by_7_pixel_box(self):
        from PIL import Image
        ink = (20, 40, 15)
        for percent in (0, 27, 100):
            subprocess.run(
                [str(self.directory / "system")],
                env=dict(self.env, DRAW_GAUGE="1", RATE=str(percent)),
                capture_output=True, text=True, check=True)
            with Image.open(self.root / "system.ppm") as image:
                self.assertTrue(all(image.getpixel((x, 10)) == ink for x in range(10, 59)))
                self.assertTrue(all(image.getpixel((x, 16)) == ink for x in range(10, 59)))
                for y in range(43):
                    for x in range(160):
                        if not (10 <= x < 59 and 10 <= y < 17):
                            self.assertNotEqual(image.getpixel((x, y)), ink)
                self.assertEqual(image.getpixel((57, 13)) == ink, percent == 100)


if __name__ == "__main__":
    unittest.main()
