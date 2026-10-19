"""Shared compiler setup for fixtures that include the native LCD renderer."""
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def compile_renderer_fixture(source, output):
    flags = shlex.split(subprocess.check_output(
        ["pkg-config", "--cflags", "--libs", "freetype2"], text=True))
    subprocess.run([
        "gcc", "-I/usr/local/include", "-L/usr/local/lib",
        f'-DPROJECT_DIR="{ROOT}"', "-Wl,-rpath,/usr/local/lib",
        str(source), "-o", str(output), "-lg15render", "-lm", *flags,
    ], check=True)
