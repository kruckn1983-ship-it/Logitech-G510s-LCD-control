"""Built-in digital clock rendering without hardware or locale dependencies."""
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import tempfile
import unittest
from native_support import compile_renderer_fixture

ROOT = Path(__file__).resolve().parents[1]


class ClockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.directory = Path(cls.tmp.name)
        source = cls.directory / "clock.c"
        source.write_text(
            '#define time fixture_time\n#define main lcd_main\n'
            f'#include "{ROOT / "src/g510_lcd_stats.c"}"\n'
            '#undef main\n#undef time\n'
            'time_t fixture_time(time_t *out) {\n'
            ' time_t now=(time_t)strtoll(getenv("NOW"),NULL,10);\n'
            ' if(out) *out=now;return now;\n}\n'
            'int main(int argc,char **argv) {\n'
            ' if(getenv("VARIANT")) {\n'
            '  g15canvas c G15_CANVAS_AUTO={0};g15r_initCanvas(&c);\n'
            '  draw_clock_screen(&c);write_ppm(&c,argv[1]);return 0;\n'
            ' }\n'
            ' if(getenv("DIRECT")) {\n'
            '  g15canvas c G15_CANVAS_AUTO={0};g15r_initCanvas(&c);\n'
            '  draw_clock_screen(&c);write_ppm(&c,argv[1]);\n'
            '  const char *keys[]={"EXPECT_HM","EXPECT_SECONDS","EXPECT_DATE"};\n'
            '  int fonts[]={G15_TEXT_HUGE,G15_TEXT_LARGE,G15_TEXT_SMALL};\n'
            '  for(int i=0;i<3;i++) {\n'
            '   g15canvas ref G15_CANVAS_AUTO={0};g15r_initCanvas(&ref);\n'
            '   g15r_renderString(&ref,(unsigned char*)getenv(keys[i]),0,fonts[i],0,0);\n'
            '   char path[1024];snprintf(path,sizeof(path),"%s/%d.ppm",getenv("REF_DIR"),i);\n'
            '   write_ppm(&ref,path);\n'
            '  }return 0;\n'
            ' }\n'
            ' if(getenv("ALL_TIMES")) {\n'
            '  for(int font=2;font<=3;font++)for(int h=0;h<24;h++)for(int m=0;m<60;m++) {\n'
            '   char value[8];snprintf(value,sizeof(value),font==3?"%02d:%02d":"%02d",font==3?h:m,m);\n'
            '   if(measure_builtin_text_width(value,font)>(font==3?31:15))return 9;\n'
            '   g15canvas ref G15_CANVAS_AUTO={0};g15r_initCanvas(&ref);\n'
            '   g15r_renderString(&ref,(unsigned char*)value,0,font,0,0);\n'
            '   for(int y=0;y<43;y++)for(int x=0;x<160;x++)if(g15r_getPixel(&ref,x,y))\n'
            '    if(font==3?(y<1||y>10):(y>6))return 10;\n'
            '  }return 0;\n'
            ' }\n'
            ' return lcd_main(argc,argv);\n}\n')
        cls.binary = cls.directory / "clock"
        compile_renderer_fixture(source, cls.binary)

    def setUp(self):
        self.tmp_home = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_home.cleanup)
        self.home = Path(self.tmp_home.name)

    def render(self, moment, zone="UTC", local=None, preview=False):
        from PIL import Image
        local = local or moment
        weekdays = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
        date = f"{weekdays[local.weekday()]}, {local:%d.%m.%Y}"
        env = dict(os.environ, HOME=str(self.home), XDG_RUNTIME_DIR=str(self.home),
                   NOW=str(int(moment.timestamp())), TZ=zone, LC_ALL="C",
                   EXPECT_HM=local.strftime("%H:%M"), EXPECT_SECONDS=local.strftime("%S"),
                   EXPECT_DATE=date, REF_DIR=str(self.home), DIRECT="1")
        output = self.home / "clock.ppm"
        subprocess.run([str(self.binary), str(output)], env=env, check=True, capture_output=True)
        with Image.open(output) as image:
            actual = image.copy()
        expected = Image.new("RGB", (160, 43), (190, 214, 145))
        for index, crop_y, crop_h, scale, x, y in (
            (0, 1, 10, 3, 14, 1), (1, 0, 7, 2, 116, 17)):
            with Image.open(self.home / f"{index}.ppm") as image:
                # The ink width is measured independently from the native font.
                ink = image.convert("RGB")
                points = [px for px in range(160) for py in range(43)
                          if ink.getpixel((px, py)) == (20, 40, 15)]
                width = max(points) + 1
                cropped = image.crop((0, crop_y, width, crop_y + crop_h))
                expected.paste(cropped.resize((width * scale, crop_h * scale),
                                             Image.Resampling.NEAREST), (x, y))
        with Image.open(self.home / "2.ppm") as image:
            points = [x for x in range(160) for y in range(6)
                      if image.getpixel((x, y)) == (20, 40, 15)]
            width = max(points) + 1
            expected.paste(image.crop((0, 0, width, 6)), ((160 - width) // 2, 36))
        # Seconds caption and the separator are the only decorative pixels.
        for y in range(43):
            for x in range(160):
                if (116 <= x < 146 and 6 <= y < 11) or y == 33:
                    continue
                self.assertEqual(actual.getpixel((x, y)), expected.getpixel((x, y)),
                                 (moment.isoformat(), x, y))
        self.assertTrue(all(actual.getpixel((x, 33)) == (20, 40, 15) for x in range(14, 146)))
        for row in (0, 31, 32, 34, 35, 42):
            self.assertTrue(all(actual.getpixel((x, row)) != (20, 40, 15) for x in range(160)))
        self.assertTrue(all(actual.getpixel((x, y)) != (20, 40, 15)
                            for x in (*range(14), *range(146, 160)) for y in range(43)))
        if preview:
            env.pop("DIRECT")
            subprocess.run([str(self.binary), "--preview", "1", str(output)],
                           env=env, capture_output=True, check=True)
            with Image.open(output) as image:
                self.assertEqual(image.tobytes(), actual.tobytes())
        return actual

    def test_all_hours_minutes_and_seconds_fit_fixed_digit_slots(self):
        subprocess.run([str(self.binary)], env=dict(os.environ, ALL_TIMES="1"),
                       check=True, capture_output=True)

    def test_midnight_noon_leap_day_and_year_rollover(self):
        for value in ("2026-10-19T00:00:00", "2026-10-19T11:11:11",
                      "2026-10-19T12:00:00", "2026-10-19T23:59:59",
                      "2028-02-29T08:08:08", "2026-12-31T23:59:59",
                      "2027-01-01T00:00:00"):
            with self.subTest(value=value):
                self.render(datetime.fromisoformat(value).replace(tzinfo=timezone.utc))

    def test_every_german_weekday_fits_and_ignores_process_locale(self):
        for day in range(19, 26):
            self.render(datetime(2026, 10, day, 21, 58, 37, tzinfo=timezone.utc))

    def test_system_timezone_and_preview_use_identical_clock(self):
        from zoneinfo import ZoneInfo
        moment = datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        self.render(moment, zone="Europe/Berlin",
                    local=moment.astimezone(ZoneInfo("Europe/Berlin")), preview=True)

    def test_seconds_change_without_moving_time_or_date(self):
        first = self.render(datetime(2026, 10, 19, 21, 58, 37, tzinfo=timezone.utc))
        second = self.render(datetime(2026, 10, 19, 21, 58, 38, tzinfo=timezone.utc))
        self.assertEqual(first.crop((0, 0, 116, 43)).tobytes(),
                         second.crop((0, 0, 116, 43)).tobytes())
        self.assertEqual(first.crop((0, 33, 160, 43)).tobytes(),
                         second.crop((0, 33, 160, 43)).tobytes())
        self.assertNotEqual(first.crop((116, 17, 146, 31)).tobytes(),
                            second.crop((116, 17, 146, 31)).tobytes())

    def render_variant(self, index, moment, *, preview=False):
        from PIL import Image
        data = self.home / ".local/share/g510-lcd"
        data.mkdir(parents=True, exist_ok=True)
        (data / "clock_layout").write_text(f"{index}\n")
        output = self.home / "variant.ppm"
        env = dict(os.environ, HOME=str(self.home), XDG_RUNTIME_DIR=str(self.home),
                   NOW=str(int(moment.timestamp())), TZ="UTC", LC_ALL="C", VARIANT="1")
        subprocess.run([str(self.binary), str(output)], env=env, capture_output=True, check=True)
        with Image.open(output) as image:
            actual = image.copy()
        if preview:
            env.pop("VARIANT")
            subprocess.run([str(self.binary), "--preview", "1", str(output)],
                           env=env, capture_output=True, check=True)
            with Image.open(output) as image:
                self.assertEqual(actual.tobytes(), image.tobytes())
        return actual

    def test_20_distinct_designs_use_same_saved_layout_in_live_and_preview(self):
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        from g510_screen_keys import CLOCK_LAYOUTS
        self.assertEqual(len(CLOCK_LAYOUTS), 20)
        images = [
            self.render_variant(i, datetime(2026, 10, 22, 23, 58, 37, tzinfo=timezone.utc),
                                preview=True).tobytes()
            for i in range(len(CLOCK_LAYOUTS))
        ]
        self.assertEqual(len(set(images)), 20)

    def test_every_design_keeps_edge_margins_for_all_weekdays_and_time_extremes(self):
        ink = (20, 40, 15)
        for index in range(20):
            for day, hour, minute, second in ((19, 0, 0, 0), (20, 11, 11, 11),
                                              (21, 12, 0, 0), (22, 23, 59, 59),
                                              (23, 8, 8, 8), (24, 20, 22, 44), (25, 18, 30, 15)):
                with self.subTest(layout=index, day=day):
                    image = self.render_variant(index, datetime(
                        2026, 10, day, hour, minute, second, tzinfo=timezone.utc))
                    self.assertEqual(image.size, (160, 43))
                    self.assertTrue(any(image.getpixel((x, y)) == ink
                                        for x in range(160) for y in range(43)))
                    for x in range(160):
                        self.assertNotEqual(image.getpixel((x, 0)), ink)
                        self.assertNotEqual(image.getpixel((x, 42)), ink)
                    for y in range(43):
                        self.assertNotEqual(image.getpixel((0, y)), ink)
                        self.assertNotEqual(image.getpixel((159, y)), ink)

    def test_invalid_layout_is_explicit_and_not_replaced_by_default(self):
        for value in ("-1", "20", "", "garbage", "1\n2", "1\0junk"):
            data = self.home / ".local/share/g510-lcd"
            data.mkdir(parents=True, exist_ok=True)
            file = data / "clock_layout"
            file.write_text(value)
            result = subprocess.run(
                [str(self.binary), str(self.home / "error.ppm")],
                env=dict(os.environ, HOME=str(self.home), XDG_RUNTIME_DIR=str(self.home),
                         NOW="1792440000", TZ="UTC", VARIANT="1"),
                capture_output=True, text=True, check=True)
            self.assertIn("invalid clock layout", result.stderr)
            self.assertEqual(file.read_text(), value)

    def test_each_design_updates_seconds_without_changing_its_saved_selection(self):
        for index in range(20):
            with self.subTest(layout=index):
                before = self.render_variant(index, datetime(2026, 10, 22, 21, 58, 37, tzinfo=timezone.utc))
                after = self.render_variant(index, datetime(2026, 10, 22, 21, 58, 38, tzinfo=timezone.utc))
                self.assertNotEqual(before.tobytes(), after.tobytes())
                self.assertEqual((self.home / ".local/share/g510-lcd/clock_layout").read_text(), f"{index}\n")

    def test_seconds_progress_is_empty_at_zero_full_at_59_and_stays_in_its_frame(self):
        for second, filled in ((0, False), (59, True)):
            image = self.render_variant(13, datetime(2026, 10, 22, 21, 58, second, tzinfo=timezone.utc))
            for y in (28, 29):
                self.assertTrue(all((image.getpixel((x, y)) == (20, 40, 15)) == filled
                                    for x in range(17, 143)))
            for x in range(15, 145):
                self.assertEqual(image.getpixel((x, 26)), (20, 40, 15))
                self.assertEqual(image.getpixel((x, 31)), (20, 40, 15))

    def test_analog_hands_do_not_overwrite_12_and_6_numerals(self):
        reference = self.render_variant(9, datetime(2026, 10, 22, 3, 15, 0, tzinfo=timezone.utc))
        for hour, minute in ((0, 0), (6, 30), (11, 59), (12, 0), (18, 30)):
            image = self.render_variant(9, datetime(2026, 10, 22, hour, minute, 0, tzinfo=timezone.utc))
            for box in ((75, 7, 85, 12), (77, 25, 83, 30)):
                self.assertEqual(image.crop(box).tobytes(), reference.crop(box).tobytes())


if __name__ == "__main__":
    unittest.main()
