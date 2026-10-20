"""Login-time backlight restoration without touching the actual keyboard."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BacklightRestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="g510 backlight ")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.led = self.home / "led"
        self.led.mkdir()
        self.saved = self.home / ".local/share/g510-lcd/set-backlight-color.sh"
        self.saved.parent.mkdir(parents=True)
        self.saved.write_text(
            '#!/bin/bash\n'
            f'echo 255 > "{self.led}/brightness"\n'
            f'echo "0 255 0" > "{self.led}/multi_intensity"\n')
        self.script = self.home / "restore.sh"
        self.script.write_text(
            (ROOT / "scripts/restore-backlight.sh").read_text().replace(
                "/sys/class/leds/g15::kbd_backlight", str(self.led)))
        self.tools = self.home / "tools"
        self.tools.mkdir()
        self.sleep = self.tools / "sleep"
        self.sleep.write_text("#!/bin/sh\nexit 0\n")
        self.sleep.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home),
                        PATH=f"{self.tools}:{os.environ['PATH']}")

    def run_restore(self, *arguments):
        return subprocess.run(
            ["bash", str(self.script), *arguments], env=self.env,
            capture_output=True, text=True, timeout=5)

    def ready(self):
        for name in ("brightness", "multi_intensity"):
            (self.led / name).write_text("0\n")

    def test_restores_saved_color_without_login_session_lookup(self):
        self.ready()
        loginctl = self.tools / "loginctl"
        loginctl.write_text("#!/bin/sh\necho 'must not query seat0' >&2\nexit 99\n")
        loginctl.chmod(0o755)
        original = self.saved.read_bytes()
        result = self.run_restore("--user")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.led / "brightness").read_text(), "255\n")
        self.assertEqual((self.led / "multi_intensity").read_text(), "0 255 0\n")
        self.assertEqual(self.saved.read_bytes(), original)

    def test_waits_until_led_device_is_available(self):
        self.sleep.write_text(
            "#!/bin/sh\n"
            f'touch "{self.led}/brightness" "{self.led}/multi_intensity"\n')
        result = self.run_restore("--user")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.led / "multi_intensity").read_text(), "0 255 0\n")

    def test_missing_device_reports_failure_instead_of_success(self):
        result = self.run_restore("--user")
        self.assertEqual(result.returncode, 1)
        self.assertIn("not writable after 30 seconds", result.stderr)

    def test_no_saved_color_is_explicitly_reported_without_changing_leds(self):
        self.ready()
        self.saved.unlink()
        result = self.run_restore("--user")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no saved backlight color", result.stdout)
        self.assertEqual((self.led / "multi_intensity").read_text(), "0\n")

    def test_saved_script_failure_is_not_masked_by_a_later_success(self):
        self.ready()
        self.saved.write_text('false\necho "should not run"\n')
        result = self.run_restore("--user")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("should not run", result.stdout)

    def test_rejects_unknown_arguments(self):
        result = self.run_restore("--unknown")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Usage:", result.stderr)

    def test_hotplug_without_session_remains_a_noop(self):
        loginctl = self.tools / "loginctl"
        loginctl.write_text("#!/bin/sh\nexit 0\n")
        loginctl.chmod(0o755)
        self.ready()
        result = self.run_restore()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.led / "multi_intensity").read_text(), "0\n")

    def test_service_is_enabled_by_installation_and_packaged(self):
        service = (ROOT / "services/g510-backlight.service").read_text()
        self.assertIn('restore-backlight.sh" --user', service)
        self.assertIn("WantedBy=default.target", service)
        self.assertIn("Restart=on-failure", service)
        install = (ROOT / "install.sh").read_text()
        self.assertIn("g510-macro-daemon g510-backlight g510-game-colors; do", install)
        self.assertIn("g510-macro-daemon.service g510-backlight.service", install)
        package = (ROOT / "packaging/g510-lcd/PKGBUILD").read_text()
        self.assertIn("g510-macro-daemon g510-backlight g510-game-colors; do", package)
        self.assertIn('scripts/restore-backlight.sh"', package)
