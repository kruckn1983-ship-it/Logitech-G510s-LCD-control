#!/usr/bin/env python3
"""Hinterlegt ein eigenes Logo fuer ein Steam-Spiel.

Aufruf: add-game-logo.py <appid> <bild.png>   (Logo setzen)
        add-game-logo.py <appid> --remove     (eigenes Logo entfernen)
"""
import os
import sys

BASE = os.path.expanduser("~/.local/share/g510-lcd")


def main():
    if len(sys.argv) != 3 or not sys.argv[1].isdigit():
        print(__doc__)
        return 1
    appid, arg = sys.argv[1], sys.argv[2]
    target = os.path.join(BASE, "custom_logos", f"{appid}.png")
    marker = os.path.join(BASE, "custom_logos", f"{appid}.optimized")
    if arg == "--remove":
        if os.path.isfile(target):
            os.remove(target)
        if os.path.isfile(marker):
            os.remove(marker)
    else:
        from PIL import Image
        os.makedirs(os.path.dirname(target), exist_ok=True)
        Image.open(arg).save(target)
        with open(marker, "w") as file:
            file.write("1\n")
    # Der Dienst erzeugt das Logo beim naechsten Spielstart neu.
    for ext in ("bin", "size"):
        cached = os.path.join(BASE, "game_logos", f"{appid}.{ext}")
        if os.path.isfile(cached):
            os.remove(cached)
    print(f"Fertig: Logo fuer {appid} " + ("entfernt." if arg == "--remove" else "gesetzt."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
