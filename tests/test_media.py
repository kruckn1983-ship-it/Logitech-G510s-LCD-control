"""Regression tests for media detection; no keyboard or audio server required."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from native_support import compile_renderer_fixture


ROOT = Path(__file__).resolve().parents[1]
SEP = "\x1f"


def player(name="vlc", title="Film", status="Playing", url="file:///film.mkv",
           position="10000000", length="120000000", artist=""):
    return SEP.join((name, title, artist, position, length, status, url)) + "\n"


def stream(name, role="", event="", corked=False):
    return (
        "Sink Input #1\n"
        f"\tCorked: {'yes' if corked else 'no'}\n"
        f'\t\tmedia.name = "{name}"\n'
        '\t\tapplication.name = "radiotray-ng"\n'
        f'\t\tmedia.role = "{role}"\n'
        f'\t\tevent.id = "{event}"\n'
    )


class MediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.directory = Path(cls.tmp.name)
        harness = cls.directory / "media.c"
        harness.write_text(
            '#define time test_time\n'
            '#define main lcd_main\n'
            f'#include "{ROOT / "src/g510_lcd_stats.c"}"\n'
            '#undef main\n'
            '#undef time\n'
            'static time_t test_now = 100;\n'
            'time_t test_time(time_t *out) { if (out) *out = test_now; return test_now; }\n'
            'int main(int argc, char **argv) {\n'
            '  if (argc > 1) return lcd_main(argc, argv);\n'
            '  if (getenv("TEST_DYNAMIC_SCREENS")) {\n'
            '    for (int screen = 6; screen <= 85; screen++) {\n'
            '      load_custom_screen(screen);\n'
            '      if (current_custom_screen.text_count != 1) return 10;\n'
            '      char expected[64]; snprintf(expected, sizeof(expected), "Screen %d", screen);\n'
            '      if (strcmp(current_custom_screen.texts[0].content, expected)) return 14;\n'
            '    }\n'
            '    load_custom_screen(2147483647);\n'
            '    if (current_custom_screen.count != 1 || current_custom_screen.text_count != 1) return 15;\n'
            '    if (strcmp(current_custom_screen.texts[0].content, "High ID")) return 16;\n'
            '    for (int reload = 0; reload < 3; reload++) {\n'
            '      g15canvas canvas G15_CANVAS_AUTO = {0}; g15r_initCanvas(&canvas);\n'
            '      draw_custom_screen(&canvas, 12);\n'
            '      if (current_custom_screen.text_count != 1) return 11;\n'
            '      char path[512]; snprintf(path, sizeof(path), "%s/custom-%d.ppm", getenv("MEDIA_FIXTURES"), reload);\n'
            '      write_ppm(&canvas, path);\n'
            '    }\n'
            '    load_custom_screen(2);\n'
            '    if (current_custom_screen.text_count != 0) return 12;\n'
            '    FILE *f = fopen(custom_screens_path(), "w"); fclose(f);\n'
            '    load_custom_screen(12);\n'
            '    if (current_custom_screen.text_count != 0) return 13;\n'
            '    return 0;\n'
            '  }\n'
            '  if (getenv("TEST_IDLE_ANIMATION")) {\n'
            '    for (int game = 0; game < 2; game++) {\n'
            '      for (int frame = 0; frame < 2; frame++) {\n'
            '        g15canvas canvas = {0}; g15r_initCanvas(&canvas);\n'
            '        draw_idle_animation_frame(&canvas, game, frame * 0.5);\n'
            '        char path[512]; snprintf(path, sizeof(path), "%s/idle-%d-%d.ppm", getenv("MEDIA_FIXTURES"), game, frame);\n'
            '        write_ppm(&canvas, path);\n'
            '      }\n'
            '    }\n'
            '    g15canvas canvas = {0}; g15r_initCanvas(&canvas);\n'
            '    g_marquee_active = 0; draw_custom_screen(&canvas, MUSIC_SCREEN);\n'
            '    printf("%d\\n", g_marquee_active);\n'
            '    g_marquee_active = 0; draw_custom_screen(&canvas, GAME_SCREEN);\n'
            '    printf("%d\\n", g_marquee_active);\n'
            '    return 0;\n'
            '  }\n'
            '  if (getenv("TEST_SCREEN_SELECTION")) {\n'
            '    write_screen(2); g_media_playing = 1; update_media_screen_selection();\n'
            '    printf("%d\\n", read_screen());\n'
            '    char marker[512]; snprintf(marker, sizeof(marker), "%s/g510lcd_manual_screen", getenv("XDG_RUNTIME_DIR"));\n'
            '    FILE *f = fopen(marker, "w"); fputs("1", f); fclose(f);\n'
            '    write_screen(3); update_media_screen_selection();\n'
            '    g_media_is_game = 1; update_media_screen_selection();\n'
            '    printf("%d\\n", read_screen());\n'
            '    write_screen(5); update_media_screen_selection();\n'
            '    printf("%d\\n", read_screen());\n'
            '    g_media_playing = 0; update_media_screen_selection();\n'
            '    test_now += 5; update_media_screen_selection();\n'
            '    printf("%d %d\\n", read_screen(), access(marker, F_OK));\n'
            '    g_media_playing = 1; g_media_is_game = 0; update_media_screen_selection();\n'
            '    printf("%d\\n", read_screen()); return 0;\n'
            '  }\n'
            '  while (getchar() != EOF) {\n'
            '    update_media_info();\n'
            '    printf("%d|%s|%s|%s\\n", g_media_playing, g_media_title,\n'
            '           g_media_artist, g_media_elapsed);\n'
            '    fflush(stdout);\n'
            '  }\n'
            '  return 0;\n'
            '}\n'
        )
        compile_renderer_fixture(harness, cls.directory / "media")
        for command, fixture in (("playerctl", "players"), ("pactl", "streams")):
            path = cls.directory / command
            path.write_text(f'#!/bin/sh\nexec /usr/bin/cat "$MEDIA_FIXTURES/{fixture}"\n')
            path.chmod(0o755)

    def poll(self, snapshots):
        env = dict(os.environ, MEDIA_FIXTURES=str(self.directory),
                   PATH=f"{self.directory}:{os.environ['PATH']}")
        process = subprocess.Popen(
            [str(self.directory / "media")], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, text=True, env=env)
        try:
            results = []
            for players, streams in snapshots:
                (self.directory / "players").write_text(players)
                (self.directory / "streams").write_text(streams)
                process.stdin.write("\n")
                process.stdin.flush()
                results.append(process.stdout.readline().rstrip("\n").split("|"))
            process.stdin.close()
            self.assertEqual(process.wait(timeout=10), 0)
            return results
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()

    def test_system_sounds_do_not_activate_media(self):
        for audio in (
            stream("desktop-login"),
            stream("Ping", role="event"),
            stream("Ping", role="notification"),
            stream("Ping", event="message-new-instant"),
        ):
            with self.subTest(audio=audio):
                self.assertEqual(self.poll([("", audio)])[0], ["0", "", "", ""])

    def test_many_custom_screens_render_and_reload_without_ghosts(self):
        with tempfile.TemporaryDirectory() as home:
            config = Path(home) / ".local/share/g510-lcd/custom_screens.txt"
            config.parent.mkdir(parents=True)
            config.write_text("".join(
                f"SCREEN L{number}\nTEXT content2=Screen%20{number} x=2 y=2 font=0\n"
                for number in range(6, 86)) +
                "SCREEN L2147483647\nTEXT content2=High%20ID x=2 y=2 font=0\n"
                "ELEMENT sensor=CPU_PCT style=number x=2 y=14 width=40 font=0\n")
            for fixture in ("players", "streams"):
                (self.directory / fixture).write_text("")
            preview = self.directory / "preview-high.ppm"
            subprocess.run([str(self.directory / "media"), "--preview-editor",
                            "2147483647", str(preview)], check=True,
                           env=dict(os.environ, HOME=home,
                                    MEDIA_FIXTURES=str(self.directory),
                                    PATH=f"{self.directory}:{os.environ['PATH']}"))
            self.assertIn("label_x1=2 label_y1=14",
                          Path(str(preview) + ".meta").read_text())
            subprocess.run([str(self.directory / "media")], check=True,
                           env=dict(os.environ, HOME=home, TEST_DYNAMIC_SCREENS="1",
                                    MEDIA_FIXTURES=str(self.directory)))
        from PIL import Image
        with Image.open(preview) as image:
            self.assertEqual(image.size, (160, 43))
            self.assertGreater(len(set(image.tobytes())), 1)
        frames = []
        for frame in range(3):
            with Image.open(self.directory / f"custom-{frame}.ppm") as image:
                self.assertEqual(image.size, (160, 43))
                self.assertGreater(len(set(image.tobytes())), 1)
                frames.append(image.tobytes())
        self.assertEqual(frames[0], frames[1])
        self.assertEqual(frames[1], frames[2])

    def test_idle_scenes_animate_and_use_fast_redraw(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, HOME=home, TEST_IDLE_ANIMATION="1",
                       MEDIA_FIXTURES=str(self.directory))
            result = subprocess.check_output([str(self.directory / "media")],
                                             env=env, text=True)
        self.assertEqual(result.splitlines(), ["1", "1"])
        from PIL import Image
        scenes = []
        for game in range(2):
            frames = []
            for frame in range(2):
                path = self.directory / f"idle-{game}-{frame}.ppm"
                with Image.open(path) as image:
                    self.assertEqual(image.size, (160, 43))
                    frames.append(image.tobytes())
                    # Neither an empty screen nor a fully filled canvas.
                    self.assertGreater(len(set(image.tobytes())), 1)
            self.assertNotEqual(frames[0], frames[1])
            scenes.append(frames[0])
        self.assertNotEqual(scenes[0], scenes[1])

    def test_idle_animation_preserves_custom_layouts(self):
        with tempfile.TemporaryDirectory() as home:
            config = Path(home) / ".local/share/g510-lcd/custom_screens.txt"
            config.parent.mkdir(parents=True)
            content = ("SCREEN L3\nTEXT content2=Custom x=2 y=2 font=0\n"
                       "SCREEN L4\nTEXT content2=Game x=2 y=2 font=0\n")
            config.write_text(content)
            env = dict(os.environ, HOME=home, TEST_IDLE_ANIMATION="1",
                       MEDIA_FIXTURES=str(self.directory))
            result = subprocess.check_output([str(self.directory / "media")],
                                             env=env, text=True)
            self.assertEqual(result.splitlines(), ["0", "0"])
            self.assertEqual(config.read_text(), content)

    def test_manual_screen_overrides_automatic_selection_until_playback_ends(self):
        env = dict(os.environ, TEST_SCREEN_SELECTION="1",
                   XDG_RUNTIME_DIR=str(self.directory))
        result = subprocess.check_output([str(self.directory / "media")],
                                         env=env, text=True)
        self.assertEqual(result.splitlines(), ["3", "3", "5", "5 -1", "3"])

    def test_radio_updates_and_ignores_system_sound(self):
        result = self.poll([
            ("", stream("desktop-login") + stream("Artist - First")),
            ("", stream("Artist - Second")),
            ("", stream("Artist - Second", corked=True)),
        ])
        self.assertEqual(result, [
            ["1", "First", "Artist", ""],
            ["1", "Second", "Artist", ""],
            ["0", "", "", ""],
        ])

    def test_mpris_updates_pause_and_stop(self):
        result = self.poll([
            (player(title="First"), stream("desktop-login")),
            (player(title="Second"), ""),
            (player(title="Second", status="Paused"), ""),
            (player(title="Second", status="Stopped"), ""),
            ("", ""),
        ])
        self.assertEqual([r[:2] for r in result], [
            ["1", "First"], ["1", "Second"], ["0", "Second"],
            ["0", ""], ["0", ""],
        ])

    def test_active_radio_replaces_paused_player_without_stale_time(self):
        result = self.poll([(
            player(status="Paused"), stream("Artist - Radio"))])[0]
        self.assertEqual(result, ["1", "Radio", "Artist", ""])

    def test_timing_belongs_to_selected_player(self):
        players = player(position="4000000", length="60000000")
        players += player(name="plasma-browser-integration", title="Video",
                          url="https://example.org/video",
                          position="7000000", length="90000000")
        result = self.poll([(players, "")])[0]
        self.assertEqual(result[1], "Video")
        self.assertEqual(result[3], "0:07/1:30")

    def test_matching_browser_exports_share_raw_timing(self):
        players = player(title="Video", url="https://example.org/video")
        players += player(name="plasma-browser-integration", title="Video",
                          url="https://example.org/video", position="999000000")
        self.assertEqual(self.poll([(players, "")])[0][3], "0:10/2:00")


if __name__ == "__main__":
    unittest.main()
