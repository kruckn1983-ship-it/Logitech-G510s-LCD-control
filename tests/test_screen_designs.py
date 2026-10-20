"""Built-in designs use the same native renderer as the device and preview."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from native_support import compile_renderer_fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import g510_screen_keys as keys


FIXTURE = r'''
#include <stdio.h>
#include <dirent.h>
#include <time.h>
#include <string.h>
static FILE *fixture_fopen(const char *, const char *);
static DIR *fixture_opendir(const char *);
static int fixture_clock(clockid_t, struct timespec *);
static time_t fixture_time(time_t *);
#define fopen fixture_fopen
#define opendir fixture_opendir
#define clock_gettime fixture_clock
#define time fixture_time
#define main lcd_main
#include "RENDERER"
#undef main
#undef fopen
#undef opendir
#undef clock_gettime
#undef time
static FILE *fixture_fopen(const char *path, const char *mode) {
    char mapped[1024];
    if (!strncmp(path, "/proc/", 6)) {
        snprintf(mapped, sizeof(mapped), "%s/%s", getenv("HOME"), path + 6);
        return fopen(mapped, mode);
    }
    if (!strncmp(path, "/sys/", 5)) return NULL;
    return fopen(path, mode);
}
static DIR *fixture_opendir(const char *path) {
    if (!strncmp(path, "/sys/", 5)) return NULL;
    return opendir(path);
}
static int fixture_clock(clockid_t id, struct timespec *out) {
    (void)id;
    double seconds = getenv("SECONDS") ? atof(getenv("SECONDS")) : (getenv("SCROLL") ? 4 : 0);
    out->tv_sec = (time_t)seconds;
    out->tv_nsec = (long)((seconds - out->tv_sec) * 1e9); return 0;
}
static time_t fixture_time(time_t *out) {
    time_t now = 1792432717; if (out) *out = now; return now;
}
int main(int argc, char **argv) {
    if (argc < 3) return 2;
    int screen = atoi(argv[1]);
    g_preview_editor_mode = 1;
    for (int i = 0; i < 20; i++) {
        cpu_core_valid[i] = 1; cpu_core_percent[i] = (i + 1) * 5;
    }
    g_nvidia_gpu_temp_c = 57; g_nvidia_gpu_percent = 65;
    g_nvidia_vram_used = 3000000000ULL; g_nvidia_vram_total = 10000000000ULL;
    g_net_rate_valid = !getenv("UNAVAILABLE");
    snprintf(g_net_iface, sizeof(g_net_iface), "enp255s255f255");
    snprintf(g_net_ipv4, sizeof(g_net_ipv4), "255.255.255.255");
    for (int i = 0; i < 60; i++) {
        g_net_down_kbps = i % 15 * 1000;
        g_net_up_kbps = (i + 7) % 15 * 100;
        append_network_history();
    }
    g_net_down_kbps = 1234; g_net_up_kbps = 128;
    if (getenv("RATE")) g_net_up_kbps = g_net_down_kbps = atof(getenv("RATE"));
    g_media_playing = !getenv("IDLE") && !getenv("PAUSED");
    if (!getenv("IDLE")) {
        snprintf(g_media_title, sizeof(g_media_title), "%s",
                 getenv("TITLE") ? getenv("TITLE") : "Test Song");
        snprintf(g_media_artist, sizeof(g_media_artist), "%s",
                 getenv("ARTIST") ? getenv("ARTIST") : "Test Artist");
        snprintf(g_media_elapsed, sizeof(g_media_elapsed), "1:23/3:45");
        g_media_progress_pct = 37;
    }
    for (int i = 0; i < VIZ_NUM_BARS; i++) g_viz_bars[i] = (i % 9 + 1) / 10.0;
    if (screen == 4 && !getenv("IDLE")) {
        g_media_is_game = 1;
        if (getenv("LOGO")) {
            g_game_logo_active = 1;
            snprintf(g_game_logo.path, sizeof(g_game_logo.path), "fixture.bin");
            g_game_logo.width = 160; g_game_logo.height = 43;
        } else {
            layout_game_title("Test Game");
            g_game_title_active = 1;
        }
    }
    if (getenv("THREADS_ONLY")) {
        g15canvas c G15_CANVAS_AUTO = {0}; g15r_initCanvas(&c);
        design_threads(&c, 0, 0, 160, 40, 2);
        if (getenv("LAST_THREAD")) {
            cpu_core_percent[19] = 0;
            g15r_clearScreen(&c, G15_COLOR_WHITE);
            design_threads(&c, 0, 0, 160, 40, 2);
        }
        write_ppm(&c, argv[2]); return 0;
    }
    if (getenv("READ_ONLY")) {
        printf("%d\n", read_screen_design(screen)); return 0;
    }
    if (getenv("CHECK_GEOMETRY")) {
        for (int i = 0; i < 19; i++) {
            const media_design_t *d = &media_designs[i];
            design_rect_t boxes[] = {d->title, d->artist, d->elapsed, d->visualizer, d->progress};
            for (int j = 0; j < 5; j++) {
                design_rect_t a = boxes[j]; if (!a.w) continue;
                if (a.x < 0 || a.y < 0 || a.x + a.w > 160 || a.y + a.h > 43) return 41;
                for (int k = j + 1; k < 5; k++) {
                    design_rect_t b = boxes[k]; if (!b.w) continue;
                    if (a.x < b.x + b.w && a.x + a.w > b.x &&
                        a.y < b.y + b.h && a.y + a.h > b.y) return 42;
                }
            }
            design_rect_t a = game_designs[i].logo;
            if (a.x < 0 || a.y < 0 || a.x + a.w > 160 || a.y + a.h > 43) return 43;
        }
        return 0;
    }
    if (getenv("VISUALIZER_ONLY")) {
        g15canvas c G15_CANVAS_AUTO = {0}; g15r_initCanvas(&c);
        design_visualizer(&c, (design_rect_t){70, 10, 40, 20});
        for (int y = 0; y < 43; y++) for (int x = 0; x < 160; x++)
            if (g15r_getPixel(&c, x, y) && (x < 70 || x >= 110 || y < 10 || y >= 30))
                return 44;
        write_ppm(&c, argv[2]); return 0;
    }
    if (getenv("FULLSCREEN_ONLY")) {
        g15canvas scene G15_CANVAS_AUTO = {0}, output G15_CANVAS_AUTO = {0};
        g15r_initCanvas(&scene); g15r_initCanvas(&output);
        for (int y = 0; y < 25; y++)
            g15r_setPixel(&scene, y * 6, y + 5, G15_COLOR_BLACK);
        draw_fullscreen_animation(&output, &scene, 5, 25);
        write_ppm(&output, argv[2]); return 0;
    }
    if (getenv("PORTAL_CUBE_ONLY")) {
        g15canvas c G15_CANVAS_AUTO = {0}; g15r_initCanvas(&c);
        arcade_portal_cube(&c, atof(getenv("SECONDS")));
        write_ppm(&c, argv[2]); return 0;
    }
    int count = g_net_history.count;
    current_custom_screen.visualizer_count = 1;
    g15canvas c G15_CANVAS_AUTO = {0}; g15r_initCanvas(&c);
    draw_custom_screen(&c, screen);
    if (g_net_history.count != count) return 31;
    write_ppm(&c, argv[2]);
    if (read_screen_design(screen) > 0 &&
        (g_element_bounds_count || g_game_element_bounds_count ||
         current_custom_screen.visualizer_count)) return 32;
    if ((screen == 3 || screen == 4) && getenv("IDLE") && !g_marquee_active) return 33;
    return 0;
}
'''


class ScreenDesignRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        source = cls.directory / "designs.c"
        source.write_text(FIXTURE.replace("RENDERER", str(ROOT / "src/g510_lcd_stats.c")))
        cls.binary = cls.directory / "designs"
        compile_renderer_fixture(source, cls.binary)

    def setUp(self):
        self.temporary_home = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_home.cleanup)
        self.home = Path(self.temporary_home.name)
        self.data = self.home / ".local/share/g510-lcd"
        self.data.mkdir(parents=True)
        (self.home / "stat").write_text("cpu  50 0 0 50 0 0 0 0\n")
        (self.home / "meminfo").write_text(
            "MemTotal: 16000000 kB\nMemAvailable: 8000000 kB\n"
            "SwapTotal: 1000000 kB\nSwapFree: 750000 kB\n")
        (self.home / "uptime").write_text("12345 0\n")
        (self.home / "cpuinfo").write_text("cpu MHz : 3200\n")
        from g510_layout_store import save_custom_screens
        from g510_layouts import build_layout_preset
        save_custom_screens({"L2": build_layout_preset("system"),
                             "L3": [], "L4": [],
                             "L5": build_layout_preset("network")},
                            self.data / "custom_screens.txt")

    def render(self, screen, index, **state):
        (self.data / f"screen_design_{screen}").write_text(f"{index}\n")
        output = self.home / "output.ppm"
        result = subprocess.run(
            [str(self.binary), str(screen), str(output)], check=True, capture_output=True,
            env=dict(os.environ, HOME=str(self.home), XDG_RUNTIME_DIR=str(self.home),
                     TZ="UTC", **state))
        with Image.open(output) as image:
            self.assertEqual(image.size, (160, 43))
            return image.copy(), result

    def test_each_screen_has_twenty_distinct_nonempty_designs_including_idle(self):
        for state in ({}, {"IDLE": "1"}):
            for screen in (2, 3, 4, 5):
                with self.subTest(screen=screen, state=state):
                    images = [self.render(screen, index, **state)[0] for index in range(20)]
                    self.assertEqual(len({image.tobytes() for image in images}), 20)
                    for index, image in enumerate(images):
                        ink = sum(image.getpixel((x, y)) == (20, 40, 15)
                                  for y in range(43) for x in range(160))
                        self.assertGreater(ink, 25, (screen, index))
                        self.assertLess(ink, 160 * 43, (screen, index))

    def test_default_missing_and_explicit_zero_preserve_existing_layout_and_files(self):
        from g510_layout_store import save_custom_screens
        from g510_layouts import build_layout_preset
        # Exercise actual existing custom layouts, not just the automatic defaults.
        save_custom_screens(
            {f"L{s}": build_layout_preset("network" if s == 5 else "system")
             for s in (2, 3, 4, 5)}, self.data / "custom_screens.txt")
        before = (self.data / "custom_screens.txt").read_bytes()
        for screen in (2, 3, 4, 5):
            first, _ = self.render(screen, 0)
            (self.data / f"screen_design_{screen}").unlink()
            output = self.home / "missing.ppm"
            subprocess.run([str(self.binary), str(screen), str(output)], check=True,
                           capture_output=True, env=dict(os.environ, HOME=str(self.home), TZ="UTC"))
            with Image.open(output) as image:
                self.assertEqual(first.tobytes(), image.tobytes())
            for index in range(1, 20):
                self.render(screen, index)
        self.assertEqual((self.data / "custom_screens.txt").read_bytes(), before)

    def test_native_selection_rejects_invalid_input_and_reports_errors(self):
        path = self.data / "screen_design_2"
        for invalid in ("", "-1", "20", "1.5", "x", "1\n2", "９", "1\x00junk"):
            path.write_text(invalid)
            result = subprocess.run(
                [str(self.binary), "2", "-"], capture_output=True, text=True, check=True,
                env=dict(os.environ, HOME=str(self.home), READ_ONLY="1"))
            self.assertEqual(result.stdout.strip(), "-1", repr(invalid))
            self.assertIn("invalid screen design", result.stderr)

    def test_all_media_titles_artists_and_paused_metadata_are_visible(self):
        for index in range(1, 20):
            playing, _ = self.render(3, index)
            paused, _ = self.render(3, index, PAUSED="1")
            idle, _ = self.render(3, index, IDLE="1")
            self.assertNotEqual(playing.tobytes(), idle.tobytes())
            self.assertNotEqual(paused.tobytes(), idle.tobytes())
            other, _ = self.render(3, index, TITLE="Other Song")
            self.assertNotEqual(playing.tobytes(), other.tobytes(), index)
            other, _ = self.render(3, index, ARTIST="Other Artist")
            self.assertNotEqual(playing.tobytes(), other.tobytes(), index)

    def test_long_media_titles_scroll_without_touching_other_design_regions(self):
        for index in range(1, 20):
            title = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 2 + "WWWWWWWW"
            first, _ = self.render(3, index, TITLE=title)
            second, _ = self.render(3, index, TITLE=title, SCROLL="1")
            self.assertTrue(first.tobytes() != second.tobytes(), index)

    def test_twentieth_cpu_thread_is_real_and_independent(self):
        first, _ = self.render(2, 2, THREADS_ONLY="1")
        second, _ = self.render(2, 2, THREADS_ONLY="1", LAST_THREAD="1")
        self.assertNotEqual(first.tobytes(), second.tobytes())
        self.assertEqual(first.crop((0, 0, 144, 43)).tobytes(),
                         second.crop((0, 0, 144, 43)).tobytes())

    def test_media_regions_do_not_overlap_and_visualizer_is_clipped(self):
        subprocess.run([str(self.binary), "3", "-"], check=True, capture_output=True,
                       env=dict(os.environ, HOME=str(self.home), CHECK_GEOMETRY="1"))
        self.render(3, 1, VISUALIZER_ONLY="1")

    def test_network_rates_zero_extreme_and_unavailable_use_real_state(self):
        for index in range(1, 20):
            zero, _ = self.render(5, index, RATE="0")
            high, _ = self.render(5, index, RATE="999999999")
            missing, _ = self.render(5, index, UNAVAILABLE="1")
            if index != 14:  # IP focus displays connection/IP/history, not rate text.
                self.assertNotEqual(zero.tobytes(), high.tobytes(), index)
                self.assertNotEqual(zero.tobytes(), missing.tobytes(), index)

    def test_custom_game_logo_is_fitted_and_not_replaced_by_idle_or_title(self):
        # XBM: a large, asymmetric cross remains recognisable when reduced.
        data = bytearray(20 * 43)
        for y in range(43):
            for x in range(160):
                if x < 3 or 18 <= y < 23 or 70 <= x < 76:
                    data[y * 20 + x // 8] |= 1 << (x % 8)
        (self.data / "fixture.bin").write_bytes(data)
        for index in range(1, 20):
            logo, _ = self.render(4, index, LOGO="1")
            title, _ = self.render(4, index)
            idle, _ = self.render(4, index, IDLE="1")
            self.assertNotEqual(logo.tobytes(), title.tobytes(), index)
            self.assertNotEqual(logo.tobytes(), idle.tobytes(), index)

    def test_all_nineteen_game_idle_variants_actually_animate(self):
        for index in range(1, 20):
            frames = [self.render(4, index, IDLE="1", SECONDS=str(seconds))[0]
                      for seconds in (0, .25, .5, 1, 4, 119.75)]
            self.assertGreaterEqual(len({frame.tobytes() for frame in frames}), 5, index)
        for seconds in (.5, 4, 119.75):
            frames = [self.render(4, index, IDLE="1", SECONDS=str(seconds))[0]
                      for index in range(1, 20)]
            self.assertEqual(len({frame.tobytes() for frame in frames}), 19, seconds)

    def test_game_idle_animation_does_not_replace_running_game_and_resumes_afterwards(self):
        for index in range(1, 20):
            idle, _ = self.render(4, index, IDLE="1", SECONDS="0.5")
            game, _ = self.render(4, index, SECONDS="0.5")
            later, _ = self.render(4, index, SECONDS="1.5")
            self.assertEqual(game.tobytes(), later.tobytes(), index)
            self.assertNotEqual(idle.tobytes(), game.tobytes(), index)
            resumed, _ = self.render(4, index, IDLE="1", SECONDS="0.5")
            self.assertEqual(idle.tobytes(), resumed.tobytes(), index)

    def test_tetris_piece_falls_completes_four_rows_then_clears_them(self):
        frames = [self.render(4, 1, IDLE="1", SECONDS=str(t))[0]
                  for t in (0, .5, 2.75, 3.25)]
        ink, background = (20, 40, 15), (190, 214, 145)
        first, falling, landed, cleared = frames
        self.assertEqual(first.getpixel((84, 1)), ink)
        self.assertEqual(falling.getpixel((84, 1)), background)
        self.assertEqual(falling.getpixel((84, 5)), ink)
        for y in (25, 29, 33, 37):
            self.assertEqual(falling.getpixel((84, y)), background)
            self.assertEqual(landed.getpixel((84, y)), ink)
            self.assertEqual(cleared.getpixel((84, y)), background)
            self.assertEqual(landed.getpixel((60, y)), ink)
            self.assertEqual(cleared.getpixel((60, y)), background)
        self.assertEqual(cleared.getpixel((72, 3)), ink)  # Next T-piece.
        self.assertEqual(first.crop((112, 6, 137, 31)).tobytes(),
                         cleared.crop((112, 6, 137, 31)).tobytes())

    def test_pacman_eats_points_opens_mouth_and_is_followed(self):
        start, _ = self.render(4, 2, IDLE="1", SECONDS="0")
        next_frame, _ = self.render(4, 2, IDLE="1", SECONDS="0.09")
        later, _ = self.render(4, 2, IDLE="1", SECONDS="2")
        ink, background = (20, 40, 15), (190, 214, 145)
        self.assertEqual(start.getpixel((43, 21)), ink)
        self.assertEqual(later.getpixel((43, 21)), background)
        self.assertEqual(later.getpixel((92, 21)), ink)
        # Same mouth-relative pixel before and after the opening widens.
        self.assertEqual(start.getpixel((12, 24)), ink)
        self.assertEqual(next_frame.getpixel((14, 24)), background)
        # Pursuer and its eye move two pixels right with the player.
        for image, x in ((start, 124), (next_frame, 126)):
            self.assertEqual(image.getpixel((x, 23)), ink)
            self.assertEqual(image.getpixel((x - 2, 21)), background)
        self.assertNotEqual(start.crop((100, 17, 145, 27)).tobytes(),
                            later.crop((100, 17, 145, 27)).tobytes())

    def test_portal_cube_enters_right_wall_and_emerges_from_left(self):
        frames = [self.render(4, 3, IDLE="1", PORTAL_CUBE_ONLY="1",
                              SECONDS=str(t))[0] for t in (0, 1.5, 1.9, 2, 2.25, 3.9)]
        ink = (20, 40, 15)
        bounds = []
        for image in frames:
            pixels = [(x, y) for y in range(43) for x in range(160)
                      if image.getpixel((x, y)) == ink]
            bounds.append((min(x for x, _ in pixels), max(x for x, _ in pixels))
                          if pixels else None)
            self.assertTrue(all(17 < x < 143 and 17 <= y <= 25 for x, y in pixels))
        self.assertEqual(bounds, [(96, 104), (135, 142), None, None, (19, 27), (92, 100)])
        for t in (0, 1.5, 2.25):
            image, _ = self.render(4, 3, IDLE="1", SECONDS=str(t))
            for x in (17, 143):
                self.assertEqual(image.getpixel((x, 5)), ink)
            cube, _ = self.render(4, 3, IDLE="1", PORTAL_CUBE_ONLY="1", SECONDS=str(t))
            for y in range(17, 26):
                for x in range(18, 143):
                    if cube.getpixel((x, y)) == ink:
                        self.assertEqual(image.getpixel((x, y)), ink)

    def test_snake_eats_food_grows_and_turns_on_the_grid(self):
        before, _ = self.render(4, 6, IDLE="1", SECONDS="1.5")
        after, _ = self.render(4, 6, IDLE="1", SECONDS="3.5")
        ink, background = (20, 40, 15), (190, 214, 145)
        self.assertEqual(before.getpixel((106, 10)), ink)
        self.assertEqual(after.getpixel((106, 10)), background)
        # After rounding the top-right corner, the head moves left on the bottom row.
        self.assertEqual(after.getpixel((140, 30)), ink)
        for image, expected in ((before, 9), (after, 12)):
            segments = sum(image.getpixel((8 + x * 4, 10 + y * 4)) == ink
                           for y in range(6) for x in range(36))
            self.assertEqual(segments, expected)

    def test_all_nineteen_media_idle_variants_move_and_have_distinct_shapes(self):
        for index in range(1, 20):
            frames = [self.render(3, index, IDLE="1", SECONDS=str(seconds))[0]
                      for seconds in (0, .25, .5, 1, 4, 119.75)]
            self.assertGreaterEqual(len({frame.tobytes() for frame in frames}), 5, index)
        for seconds in (.5, 4, 119.75):
            frames = [self.render(3, index, IDLE="1", SECONDS=str(seconds))[0]
                      for index in range(1, 20)]
            self.assertEqual(len({frame.tobytes() for frame in frames}), 19, seconds)

    def test_media_idle_resumes_after_playback_and_does_not_replace_paused_metadata(self):
        for index in range(1, 20):
            idle, _ = self.render(3, index, IDLE="1", SECONDS="0.5")
            for state in ({}, {"PAUSED": "1"}):
                media, _ = self.render(3, index, SECONDS="0.5", **state)
                self.assertNotEqual(idle.tobytes(), media.tobytes(), (index, state))
            resumed, _ = self.render(3, index, IDLE="1", SECONDS="0.5")
            self.assertEqual(idle.tobytes(), resumed.tobytes(), index)

    def test_fullscreen_animation_maps_entire_scene_to_all_160_by_43_pixels(self):
        image, _ = self.render(3, 1, FULLSCREEN_ONLY="1")
        for y in range(43):
            for x in range(160):
                expected = (20, 40, 15) if x == y * 25 // 43 * 6 else (190, 214, 145)
                self.assertEqual(image.getpixel((x, y)), expected, (x, y))

    def test_all_forty_idle_animations_use_full_height_without_caption_rows(self):
        for screen in (3, 4):
            for index in range(20):
                image, _ = self.render(screen, index, IDLE="1", SECONDS="0.5")
                source_height = 24 if index == 0 else (43 if screen == 4 else 25)
                rows = {}
                occupied = []
                for y in range(43):
                    source = y * source_height // 43
                    row = image.crop((0, y, 160, y + 1)).tobytes()
                    if source in rows:
                        self.assertEqual(row, rows[source], (screen, index, y))
                    rows[source] = row
                    if any(image.getpixel((x, y)) == (20, 40, 15) for x in range(160)):
                        occupied.append(y)
                self.assertGreater(max(occupied) - min(occupied), 15, (screen, index))


class ScreenDesignKeyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for context in (
            patch.object(keys, "DESIGN_DATA_DIR", self.root),
            patch.object(keys, "SCREENS_PATH", self.root / "screens.json"),
            patch.dict(os.environ, XDG_RUNTIME_DIR=str(self.root)),
        ):
            context.start()
            self.addCleanup(context.stop)

    def test_l2_l3_wrap_all_twenty_and_preserve_other_screens(self):
        with patch.object(keys, "load_bindings", return_value=keys.default_bindings()), \
                patch.object(keys.subprocess, "run") as run:
            for screen in SCREEN_IDS:
                keys.show_screen(screen)
                for expected in list(range(1, 20)) + [0, 1]:
                    keys.handle_key("L3")
                    self.assertEqual(keys.load_screen_design(screen), expected)
                keys.handle_key("L2")
                self.assertEqual(keys.load_screen_design(screen), 0)
                keys.handle_key("L2")
                self.assertEqual(keys.load_screen_design(screen), 19)
                self.assertEqual(keys.read_screen(), screen)
            self.assertEqual([keys.load_screen_design(s) for s in SCREEN_IDS], [19] * 4)
            run.assert_not_called()

    def test_game_animation_catalog_includes_requested_inspirations_and_twenty_unique_choices(self):
        names = keys.SCREEN_DESIGNS[4]
        self.assertEqual(len(names), 20)
        self.assertEqual(len(set(names)), 20)
        self.assertIn("Raumschiff", names[0])
        for index, game in enumerate(("Tetris", "Pac-Man", "Portal", "Pong", "Breakout",
                                      "Snake", "Frogger", "Bomberman", "Asteroids",
                                      "Sokoban", "Minesweeper", "Flipper"), 1):
            self.assertTrue(names[index].startswith(f"{game}:"), (index, game))

    def test_design_selection_validation_and_atomic_persistence(self):
        self.assertEqual(keys.load_screen_design(2), 0)
        for value in ("", "-1", "20", "1.5", "x", "1\n2", "９", "1\x00junk"):
            keys.design_path(2).write_text(value)
            with self.assertRaises(ValueError):
                keys.load_screen_design(2)
        for value in (-1, 20, True, "2"):
            with self.assertRaises(ValueError):
                keys.save_screen_design(2, value)
        for screen in (1, 6, True, "2"):
            with self.assertRaises(ValueError):
                keys.save_screen_design(screen, 0)
        keys.save_screen_design(2, 7)
        self.assertEqual(keys.load_screen_design(2), 7)
        self.assertFalse(keys.design_path(2).with_suffix(".tmp").exists())
        keys.show_screen(1)
        with self.assertRaisesRegex(ValueError, "nur auf"):
            keys.perform_action("design_next")


SCREEN_IDS = (2, 3, 4, 5)
