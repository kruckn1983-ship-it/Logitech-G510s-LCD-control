#!/usr/bin/env python3
"""Erzeugt die LCD-Logos fuer alle installierten Steam-Spiele im Voraus.

Ergebnis: ~/.local/share/g510-lcd/game_logos/<appid>.bin und <appid>.size.
Das echte Steam-Logo wird mit png-to-lcd.py umgewandelt; nur ohne Artwork
wird der Titel als Schrift-Logo (title-to-lcd.py) gerendert.
Vorhandene Logos werden uebersprungen (mit --force neu erzeugen).
"""
import os
import re
import subprocess
import sys

HOME = os.path.expanduser("~")
SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
TITLE_CONVERTER = os.path.join(SRC_DIR, "title-to-lcd.py")
CONVERTER = os.path.join(SRC_DIR, "png-to-lcd.py")
STEAM_ROOTS = [
    f"{HOME}/.local/share/Steam",
    f"{HOME}/.steam/steam",
    f"{HOME}/.steam/root",
    f"{HOME}/.var/app/com.valvesoftware.Steam/.local/share/Steam",
]
ART_NAMES = ["logo.png", "header.jpg", "library_header.jpg",
             "library_capsule.jpg", "library_hero.jpg", "library_600x900.jpg"]
OUT_DIR = os.path.join(os.environ.get("XDG_DATA_HOME", f"{HOME}/.local/share"),
                       "g510-lcd", "game_logos")


def libraries():
    found = []
    for root in STEAM_ROOTS:
        real = os.path.realpath(root)
        if os.path.isdir(real) and real not in found:
            found.append(real)
        vdf = os.path.join(real, "steamapps", "libraryfolders.vdf")
        if os.path.isfile(vdf):
            with open(vdf, errors="replace") as f:
                for path in re.findall(r'"path"\s+"([^"]+)"', f.read()):
                    path = os.path.realpath(path.replace("\\\\", "\\"))
                    if os.path.isdir(path) and path not in found:
                        found.append(path)
    return found


def games(libs):
    seen = {}
    for lib in libs:
        steamapps = os.path.join(lib, "steamapps")
        if not os.path.isdir(steamapps):
            continue
        for name in os.listdir(steamapps):
            match = re.fullmatch(r"appmanifest_(\d+)\.acf", name)
            if not match:
                continue
            with open(os.path.join(steamapps, name), errors="replace") as f:
                title = re.search(r'"name"\s+"([^"]*)"', f.read())
            seen.setdefault(int(match.group(1)), title.group(1) if title else "?")
    return seen


def find_artwork(libs, appid):
    for art in ART_NAMES:
        for lib in libs:
            cache = os.path.join(lib, "appcache", "librarycache")
            for candidate in (f"{cache}/{appid}/{art}", f"{cache}/{appid}_{art}"):
                if os.path.isfile(candidate):
                    return candidate
            app_dir = os.path.join(cache, str(appid))
            if os.path.isdir(app_dir):
                for sub in sorted(os.listdir(app_dir)):
                    candidate = os.path.join(app_dir, sub, art)
                    if os.path.isfile(candidate):
                        return candidate
    return None


def main():
    force = "--force" in sys.argv[1:]
    libs = libraries()
    installed = games(libs)
    os.makedirs(OUT_DIR, exist_ok=True)
    done = skipped = failed = 0
    for appid, title in sorted(installed.items()):
        output = os.path.join(OUT_DIR, f"{appid}.bin")
        size_file = os.path.join(OUT_DIR, f"{appid}.size")
        if not force and os.path.isfile(output) and os.path.isfile(size_file):
            skipped += 1
            continue
        def run(cmd):
            result = subprocess.run([sys.executable] + cmd,
                                    capture_output=True, text=True)
            return result.stdout.split() if result.returncode == 0 else []

        # Wie im Dienst: echtes Steam-Logo, sonst Titel als Schrift-Logo.
        source = find_artwork(libs, appid)
        # Handgepflegte Strich-Logos (z. B. DOOM) haben Vorrang.
        custom = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "assets", "logos", f"{appid}.png")
        own = os.path.expanduser(
            f"~/.local/share/g510-lcd/custom_logos/{appid}.png")
        if os.path.isfile(own):
            source = custom = own
        elif os.path.isfile(custom):
            source = custom
        flags = ((["--upscale", "--invert-dark"] if source == own else ["--upscale"])
                 if source == custom else
                 ["--trim-transparent", "--upscale", "--invert-dark",
                  "--boost-wide", "--best-logo"])
        size = run([CONVERTER, source, output, "160", "43"] + flags) \
            if source else []
        kind = "Logo"
        if len(size) < 2:
            size = run([TITLE_CONVERTER, title, output])
            kind = "Titel-Logo"
        if len(size) < 2:
            print(f"{appid} {title}: Umwandlung fehlgeschlagen")
            failed += 1
            continue
        with open(size_file, "w") as f:
            f.write(f"{size[0]} {size[1]}\n")
        print(f"{appid} {title}: {size[0]}x{size[1]} ({kind})")
        done += 1
    print(f"Fertig: {done} erzeugt, {skipped} vorhanden, "
          f"{failed} fehlgeschlagen.")


if __name__ == "__main__":
    main()
