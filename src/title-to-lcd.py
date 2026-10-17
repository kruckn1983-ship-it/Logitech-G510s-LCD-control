#!/usr/bin/env python3
"""Rendert einen Spielnamen als fettes Schrift-Logo fuer das G510s-LCD.

Aufruf: title-to-lcd.py "<Titel>" <ausgabe.bin> [breite hoehe]
Schreibt die Bitmap im gleichen Format wie png-to-lcd.py und gibt
"<breite> <hoehe>" aus. Der Titel wird in Grossbuchstaben auf 1-4 Zeilen
so verteilt, dass die Schrift das Display moeglichst gross ausfuellt.
"""
import itertools
import os
import sys

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "/usr/share/fonts/google-noto/NotoSans-CondensedBlack.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-CondensedBlack.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSansCondensed-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSansCondensed-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Bold.ttf",
    "/usr/share/fonts/liberation/LiberationSansNarrow-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
]
LINE_GAP = 12  # Pixel bei Schriftgroesse 100
MAX_STRETCH = 1.35


def load_font():
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, 100)
        except OSError:
            continue
    sys.exit("keine passende Schrift gefunden")


def render(title, width, height):
    font = load_font()
    words = title.upper().split()
    if not words:
        sys.exit("leerer Titel")

    def line_image(text):
        box = font.getbbox(text)
        image = Image.new("L", (box[2] - box[0], box[3] - box[1]), 0)
        ImageDraw.Draw(image).text((-box[0], -box[1]), text, font=font, fill=255)
        return image

    best = None
    for count in range(1, min(len(words), 4) + 1):
        for cuts in itertools.combinations(range(1, len(words)), count - 1):
            bounds = (0,) + cuts + (len(words),)
            lines = [line_image(" ".join(words[a:b]))
                     for a, b in zip(bounds, bounds[1:])]
            total_w = max(line.width for line in lines)
            total_h = sum(line.height for line in lines) + LINE_GAP * (count - 1)
            scale = min(width / total_w, height / total_h)
            if best is None or scale > best[0]:
                best = (scale, lines)
    scale, lines = best
    total_h = sum(line.height for line in lines) + LINE_GAP * (len(lines) - 1)
    canvas = Image.new("L", (width, height), 0)
    y = (height - total_h * scale) / 2
    for line in lines:
        line_h = max(1, round(line.height * scale))
        stretch = min(width / (line.width * scale), MAX_STRETCH)
        line_w = min(width, max(1, round(line.width * scale * stretch)))
        scaled = line.resize((line_w, line_h), Image.BOX).point(
            lambda v: 255 if v > 100 else 0)
        canvas.paste(scaled, ((width - line_w) // 2, round(y)))
        y += line_h + LINE_GAP * scale
    box = canvas.getbbox()
    return canvas.crop(box) if box else canvas


def main():
    if len(sys.argv) not in (3, 5):
        sys.exit(__doc__)
    title, outfile = sys.argv[1], sys.argv[2]
    width = int(sys.argv[3]) if len(sys.argv) == 5 else 158
    height = int(sys.argv[4]) if len(sys.argv) == 5 else 43
    image = render(title, width, height)
    w, h = image.size
    row_bytes = (w + 7) // 8
    pixels = image.load()
    data = bytearray(row_bytes * h)
    for y in range(h):
        for x in range(w):
            if pixels[x, y]:
                data[y * row_bytes + x // 8] |= 1 << (x % 8)
    with open(outfile, "wb") as f:
        f.write(data)
    print(f"{w} {h}")


if __name__ == "__main__":
    main()
