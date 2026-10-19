"""Exercise the shared build entry point without services or system changes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="g510 build test ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.tools = self.root / "tools"
        self.tools.mkdir()
        self.output = self.root / "output"
        self.output.mkdir()
        self.log = self.root / "commands.jsonl"
        compiler = self.tools / "gcc"
        compiler.write_text(
            f"#!{sys.executable}\n"
            "import json, os, pathlib, sys\n"
            "args = sys.argv[1:]\n"
            "out = pathlib.Path(args[args.index('-o') + 1])\n"
            "with open(os.environ['BUILD_LOG'], 'a') as log:\n"
            "    log.write(json.dumps(args) + '\\n')\n"
            "if os.environ.get('BUILD_FAIL') == out.name:\n"
            "    print('compiler fixture failure', file=sys.stderr)\n"
            "    sys.exit(23)\n"
            "out.write_text('new ' + out.name)\n")
        compiler.chmod(0o755)
        config = self.tools / "pkg-config"
        config.write_text(
            "#!/bin/sh\n"
            'if [ -n "$PKG_CONFIG_FAIL" ]; then echo "missing freetype2" >&2; exit 7; fi\n'
            'case "$1" in --cflags) echo "-I/fixture/include";; --libs) echo "-lfreetype";; esac\n')
        config.chmod(0o755)
        self.env = dict(os.environ, PATH=f"{self.tools}:{os.environ['PATH']}",
                        BUILD_LOG=str(self.log), BUILD_FAIL="", PKG_CONFIG_FAIL="")
        for name in ("g510_lcd_stats", "g510_lcd_buttons"):
            (self.output / name).write_text("old " + name)

    def build(self, *arguments):
        return subprocess.run(
            ["bash", str(ROOT / "scripts/build.sh"), "--output-dir", str(self.output),
             *arguments], env=self.env, text=True, capture_output=True)

    def assert_original_outputs(self):
        for name in ("g510_lcd_stats", "g510_lcd_buttons"):
            self.assertEqual((self.output / name).read_text(), "old " + name)
        self.assertEqual(list(self.output.glob(".g510-build.*")), [])

    def test_success_preserves_flags_and_handles_spaces(self):
        project = str(self.root / "project checkout")
        result = self.build("--project-dir", project)
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual(len(commands), 2)
        for flag in ('-DPROJECT_DIR="' + project + '"', "-I/fixture/include",
                     "-lfreetype", "-lg15render", "-Wl,-rpath,/usr/local/lib"):
            self.assertIn(flag, commands[0])
        for name in ("g510_lcd_stats", "g510_lcd_buttons"):
            self.assertEqual((self.output / name).read_text(), "new " + name)
        self.assertEqual(list(self.output.glob(".g510-build.*")), [])

    def test_compiler_failures_leave_both_running_binaries_untouched(self):
        for name in ("g510_lcd_stats", "g510_lcd_buttons"):
            with self.subTest(program=name):
                self.env["BUILD_FAIL"] = name
                result = self.build()
                self.assertEqual(result.returncode, 23, result.stderr)
                self.assertIn("compiler fixture failure", result.stderr)
                self.assert_original_outputs()

    def test_pkg_config_failure_is_not_hidden_by_command_substitution(self):
        self.env["PKG_CONFIG_FAIL"] = "1"
        result = self.build()
        self.assertEqual(result.returncode, 7)
        self.assertIn("missing freetype2", result.stderr)
        self.assertFalse(self.log.exists())
        self.assert_original_outputs()

    def test_invalid_options_fail_explicitly_before_compiling(self):
        for args in (("--unknown",), ("--project-dir",), ("--output-dir", "")):
            with self.subTest(arguments=args):
                result = self.build(*args)
                self.assertEqual(result.returncode, 2)
                self.assertTrue(result.stderr.strip())
                self.assertFalse(self.log.exists())
                self.assert_original_outputs()
