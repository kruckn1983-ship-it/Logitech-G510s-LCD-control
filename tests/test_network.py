"""Network counters, interface changes and address regressions using fixtures."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from native_support import compile_renderer_fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class NetworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.directory = Path(cls.tmp.name)
        source = cls.directory / "network.c"
        source.write_text(
            '#include <stdio.h>\n#include <dirent.h>\n#include <time.h>\n'
            '#include <ifaddrs.h>\n#include <arpa/inet.h>\n#include <string.h>\n'
            'static FILE *fixture_fopen(const char *, const char *);\n'
            'static DIR *fixture_opendir(const char *);\n'
            'static int fixture_addresses(struct ifaddrs **);\n'
            'static void fixture_free(struct ifaddrs *);\n'
            'static int fixture_clock(clockid_t, struct timespec *);\n'
            '#define fopen fixture_fopen\n#define opendir fixture_opendir\n'
            '#define getifaddrs fixture_addresses\n#define freeifaddrs fixture_free\n'
            '#define clock_gettime fixture_clock\n#define main lcd_main\n'
            f'#include "{ROOT / "src/g510_lcd_stats.c"}"\n'
            '#undef fopen\n#undef opendir\n#undef getifaddrs\n#undef freeifaddrs\n'
            '#undef clock_gettime\n#undef main\n'
            'static const char *fixture_path(const char *path, char *out) {\n'
            ' if (!strncmp(path, "/proc/net/", 10) || !strncmp(path, "/sys/class/net", 14)) {\n'
            '  snprintf(out, 1024, "%s%s", getenv("FIXTURES"), path); return out;\n'
            ' } return path;\n}\n'
            'static FILE *fixture_fopen(const char *p, const char *m) {\n'
            ' char out[1024]; return fopen(fixture_path(p,out),m);\n}\n'
            'static DIR *fixture_opendir(const char *p) {\n'
            ' char out[1024]; return opendir(fixture_path(p,out));\n}\n'
            'static int fixture_addresses(struct ifaddrs **result) {\n'
            ' static struct ifaddrs entry; static struct sockaddr_in address;\n'
            ' static char iface[64]; char ip[64], path[1024];\n'
            ' snprintf(path,sizeof(path),"%s/address",getenv("FIXTURES"));\n'
            ' FILE *f=fopen(path,"r"); *result=NULL; if (!f) return 0;\n'
            ' int ok=fscanf(f,"%63s %63s",iface,ip)==2; fclose(f); if (!ok) return 0;\n'
            ' memset(&entry,0,sizeof(entry)); memset(&address,0,sizeof(address));\n'
            ' address.sin_family=AF_INET; inet_pton(AF_INET,ip,&address.sin_addr);\n'
            ' entry.ifa_name=iface; entry.ifa_addr=(struct sockaddr *)&address;\n'
            ' *result=&entry; return 0;\n}\n'
            'static void fixture_free(struct ifaddrs *p) { (void)p; }\n'
            'static int fixture_clock(clockid_t id, struct timespec *out) {\n'
            ' (void)id; static int tick=0; tick++; out->tv_sec=tick/2;\n'
            ' out->tv_nsec=(tick%2)*500000000L; return 0;\n}\n'
            'int main(void) {\n'
            ' if (getenv("TEST_NETWORK_CACHE_READ")) {\n'
            '  update_net_speed();\n'
            '  if (getenv("TEST_CACHE_NOW")) g_net_sampled_at=atof(getenv("TEST_CACHE_NOW"));\n'
            '  int ok=read_network_snapshot();\n'
            '  printf("%d %d %.3f %.3f\\n",ok,g_net_history.count,g_net_down_kbps,g_net_up_kbps);\n'
            '  return 0;\n'
            ' }\n'
            ' if (getenv("TEST_NETWORK_BOUNDS")) {\n'
            '  snprintf(g_net_iface,sizeof(g_net_iface),"enp255s255f255");\n'
            '  snprintf(g_net_ipv4,sizeof(g_net_ipv4),"255.255.255.255");\n'
            '  g_net_down_kbps=1023; g_net_up_kbps=999999; g_net_rate_valid=1;\n'
            '  for (int i=0;i<60;i++) {\n'
            '   g_net_down_kbps=i%15*1000; g_net_up_kbps=(i+7)%15*100;\n'
            '   append_network_history();\n'
            '  }\n'
            '  g_net_down_kbps=getenv("TEST_RATE")?atof(getenv("TEST_RATE")):1023;\n'
            '  g_net_up_kbps=999999;\n'
            '  g15canvas canvas G15_CANVAS_AUTO={0}; g15r_initCanvas(&canvas);\n'
            '  draw_custom_screen(&canvas,5);\n'
            '  for (int y=10;y<32;y++) for (int x=102;x<110;x++)\n'
            '   if (g15r_getPixel(&canvas,x,y)) return 23;\n'
            '  char scene[1024]; snprintf(scene,sizeof(scene),"%s/network.ppm",getenv("FIXTURES"));\n'
            '  write_ppm(&canvas,scene);\n'
            '  int ip_end=2+measure_builtin_label_width("IP:",0)+2+\n'
            '   measure_builtin_text_width("255.255.255.255",0);\n'
            '  if (g_element_bounds_count!=6 || g_element_bounds[3].value_x2!=ip_end) return 20;\n'
            '  if (g_element_bounds[1].value_x2>102 || g_element_bounds[2].value_x2>102) return 21;\n'
            '  g15canvas graph G15_CANVAS_AUTO={0}; g15r_initCanvas(&graph);\n'
            '  element_t el={.sensor="NET_DOWN",.style="history",.x=110,.y=10,.width=48,.height=10};\n'
            '  draw_network_history(&graph,&el);\n'
            '  int pixels=0;\n'
            '  for (int y=0;y<43;y++) for (int x=0;x<160;x++)\n'
            '   if (g15r_getPixel(&graph,x,y)) {\n'
            '    if (x<110 || x>=158 || y<10 || y>=20) return 22;\n'
            '    pixels++;\n'
            '   }\n'
            '  if (pixels<=57) return 24;\n'
            '  char image[1024]; snprintf(image,sizeof(image),"%s/graph.ppm",getenv("FIXTURES"));\n'
            '  write_ppm(&graph,image);\n'
            '  memset(&g_net_history,0,sizeof(g_net_history));\n'
            '  for (int i=0;i<2;i++) {\n'
            '   if (i) { g_net_down_kbps=0; g_net_up_kbps=0; append_network_history(); }\n'
            '   g15canvas flat G15_CANVAS_AUTO={0}; g15r_initCanvas(&flat);\n'
            '   draw_network_history(&flat,&el); pixels=0;\n'
            '   for (int y=0;y<43;y++) for (int x=0;x<160;x++) pixels+=!!g15r_getPixel(&flat,x,y);\n'
            '   if (pixels!=57) return 25;\n'
            '  }\n'
            '  for (int i=0;i<g_element_bounds_count;i++) {\n'
            '   element_bounds_t *b=&g_element_bounds[i];\n'
            '   printf("%d %d %d\\n",b->label_y1,b->label_y2,b->value_x2);\n'
            '  } return 0;\n'
            ' }\n'
            ' while (getchar()!=EOF) {\n'
            '  update_net_speed();\n'
            '  publish_network_snapshot();\n'
            '  const char *sensors[]={"NET_CONNECTION","NET_DOWN","NET_UP","NET_IPV4"};\n'
            '  for (int i=0;i<4;i++) { char value[96]; double pct;\n'
            '   get_sensor_value(sensors[i],"",&pct,value,sizeof(value));\n'
            '   printf("%s%s",i?"|":"",value);\n'
            '  } puts(""); fflush(stdout);\n'
            ' } return 0;\n}\n')
        compile_renderer_fixture(source, cls.directory / "network")

    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        self.root = Path(self.home.name)
        (self.root / "proc/net").mkdir(parents=True)
        (self.root / "sys/class/net").mkdir(parents=True)
        self.process = subprocess.Popen(
            [str(self.directory / "network")], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, text=True,
            env=dict(os.environ, FIXTURES=str(self.root), XDG_RUNTIME_DIR=str(self.root)))
        self.addCleanup(self.stop)

    def stop(self):
        self.process.stdin.close()
        self.process.wait(timeout=5)
        self.process.stdout.close()

    def snapshot(self, iface="eth0", rx=1000, tx=500, address="192.168.1.20"):
        for state in (self.root / "sys/class/net").glob("*/operstate"):
            state.write_text("down")
        if iface:
            directory = self.root / "sys/class/net" / iface
            directory.mkdir(exist_ok=True)
            (directory / "operstate").write_text("up")
        (self.root / "proc/net/route").write_text(
            f"Iface Destination Gateway Flags RefCnt Use Metric\n"
            + (f"{iface} 00000000 00000000 0001 0 0 10\n" if iface else ""))
        (self.root / "proc/net/dev").write_text(
            f"{iface}: {rx} 0 0 0 0 0 0 0 {tx} 0 0 0 0 0 0 0\n" if iface else "")
        (self.root / "address").write_text(f"{iface} {address}" if address and iface else "")
        self.process.stdin.write("\n")
        self.process.stdin.flush()
        return self.process.stdout.readline().strip().split("|")

    def test_rates_use_elapsed_time_units_and_distinguish_initial_from_zero(self):
        self.assertEqual(self.snapshot(),
                         ["LINK: eth0", "N/V", "N/V", "192.168.1.20"])
        self.assertEqual(self.snapshot(rx=2024, tx=1012)[1:3],
                         ["2 KiB/s", "1 KiB/s"])
        self.assertEqual(self.snapshot(rx=2024, tx=1012)[1:3],
                         ["0 KiB/s", "0 KiB/s"])
        self.assertEqual(self.snapshot(rx=2024 + 1048576, tx=1012)[1],
                         "2.0 MiB/s")

    def test_disconnect_switch_and_counter_reset_clear_previous_values(self):
        self.snapshot()
        self.assertEqual(self.snapshot(iface=""),
                         ["KEINE VERBINDUNG", "N/V", "N/V", "N/V"])
        self.assertEqual(self.snapshot(iface="wlan0", address="10.0.0.5"),
                         ["LINK: wlan0", "N/V", "N/V", "10.0.0.5"])
        self.assertEqual(self.snapshot(iface="wlan0", rx=100, tx=10, address="")[1:],
                         ["N/V", "N/V", "N/V"])
        self.assertEqual(self.snapshot(iface="wlan0", rx=100, tx=10, address="")[1:],
                         ["0 KiB/s", "0 KiB/s", "N/V"])

    def test_network_preset_separates_text_and_history(self):
        import g510_app as gui
        layout = gui.build_layout_preset("network")
        self.assertEqual([item["sensor"] for item in layout],
                         ["NET_CONNECTION", "NET_DOWN", "NET_UP", "NET_IPV4",
                          "NET_DOWN", "NET_UP"])
        self.assertEqual([item["y"] for item in layout], [0, 10, 22, 33, 10, 22])
        for number, history in zip(layout[1:3], layout[4:]):
            self.assertGreaterEqual(history["x"] - (number["x"] + number["max_width"]), 8)
            self.assertEqual(history["style"], "history")
            self.assertLessEqual(history["x"] + history["width"], 158)
            self.assertLessEqual(history["y"] + history["height"], 32)
        for item in layout:
            self.assertIn(item["sensor"], gui.SENSOR_LABELS)
            self.assertIn(item["sensor"], gui.SENSOR_DESCRIPTIONS)

    def test_rendered_network_layout_keeps_long_values_inside_display(self):
        from unittest.mock import patch
        import g510_app as gui
        data = self.root / ".local/share/g510-lcd"
        data.mkdir(parents=True)
        with patch.object(gui, "CUSTOM_SCREENS_FILE", data / "custom_screens.txt"):
            gui.save_custom_screens({"L5": gui.build_layout_preset("network")})
            loaded = gui.load_custom_screens()
            self.assertEqual(loaded["L5"][1]["max_width"], 100)
            self.assertEqual(loaded["L5"][4]["style"], "history")
            self.assertEqual(loaded["L5"][4]["height"], 10)
            gui.save_custom_screens(loaded)
            self.assertEqual(gui.load_custom_screens(), loaded)
        output = subprocess.check_output(
            [str(self.directory / "network")], text=True,
            env=dict(os.environ, HOME=str(self.root), TEST_NETWORK_BOUNDS="1",
                     XDG_RUNTIME_DIR=str(self.root),
                     FIXTURES=str(self.root)))
        bounds = [list(map(int, line.split())) for line in output.splitlines()]
        self.assertEqual(len(bounds), 9)  # Includes the isolated graphs used for pixel checks.
        self.assertEqual([row[0] for row in bounds[:4]], [0, 10, 22, 33])
        for row, next_y in zip(bounds, (10, 22, 33, 43)):
            self.assertLess(row[1], next_y)
            self.assertLess(row[2], 160)
        self.assertLessEqual(bounds[1][2], 102)
        self.assertLessEqual(bounds[2][2], 102)
        for rate in (0, 11, 14.3 * 1024, 1024 * 1024 * 10):
            result = subprocess.run(
                [str(self.directory / "network")], text=True, capture_output=True,
                env=dict(os.environ, HOME=str(self.root), TEST_NETWORK_BOUNDS="1",
                         XDG_RUNTIME_DIR=str(self.root), FIXTURES=str(self.root),
                         TEST_RATE=str(rate)))
            self.assertEqual(result.returncode, 0, result.stderr)

    def read_cache(self, now=None):
        env = dict(os.environ, FIXTURES=str(self.root), XDG_RUNTIME_DIR=str(self.root),
                   TEST_NETWORK_CACHE_READ="1")
        if now is not None:
            env["TEST_CACHE_NOW"] = str(now)
        return subprocess.run([str(self.directory / "network")], env=env,
                              capture_output=True, text=True, check=True)

    def test_history_rolls_at_60_samples_and_clears_on_switch_and_disconnect(self):
        self.snapshot()
        for i in range(1, 81):
            self.snapshot(rx=1000 + i * 1024, tx=500 + i * 512)
        cache = (self.root / "g510lcd_network").read_text().splitlines()
        self.assertEqual(cache[0].split()[-2:], ["1", "60"])
        self.assertEqual(len(cache), 61)
        self.assertEqual(cache[-1].split(), ["2.000000000", "1.000000000"])
        self.snapshot(iface="wlan0")
        self.assertEqual((self.root / "g510lcd_network").read_text().split()[-2:], ["0", "0"])
        self.snapshot(iface="")
        self.assertEqual((self.root / "g510lcd_network").read_text().split()[-3:], ["-", "0", "0"])

    def test_preview_reads_daemon_history_without_writing_or_adding_samples(self):
        self.snapshot()
        self.snapshot(rx=2024, tx=1012)
        file = self.root / "g510lcd_network"
        before = file.read_bytes()
        for _ in range(3):
            self.assertEqual(self.read_cache(now=1.5).stdout.strip(), "1 1 2.000 1.000")
            self.assertEqual(file.read_bytes(), before)
        self.assertEqual(self.read_cache(now=20).stdout.split()[0], "0")
        self.assertEqual(self.read_cache(now=0).stdout.split()[0], "0")
        self.assertEqual(file.read_bytes(), before)
        self.snapshot(iface="wlan0")
        file.write_bytes(before)
        self.assertEqual(self.read_cache(now=1.5).stdout.split()[0], "0")

    def test_invalid_cache_reports_error_and_does_not_render_old_history(self):
        self.snapshot()
        file = self.root / "g510lcd_network"
        for content in (
            "not a cache", "G510NET1 0.5 eth0 1 100\n",
            "G510NET1 0.5 eth0 1 1\nnan 1\n",
            "G510NET1 0.5 eth0 1 1\n1 -1\n",
            "G510NET1 0.5 eth0 1 1\n",
        ):
            file.write_text(content)
            result = self.read_cache()
            self.assertEqual(result.stdout.strip(), "0 0 0.000 0.000")
            self.assertIn("invalid network snapshot", result.stderr)
            self.assertEqual(file.read_text(), content)


if __name__ == "__main__":
    unittest.main()
