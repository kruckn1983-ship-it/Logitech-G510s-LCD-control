#!/usr/bin/env python3
# Converts a PNG (or any image Pillow can open) into a raw XBM bitmap
# file g510_lcd_stats.c can load directly via g15r_drawXBM(). Only does
# the ONE-TIME conversion step -- all runtime drawing stays in C, no
# image library needed there.
import sys
import re
import tempfile
import os
from PIL import Image, ImageOps, ImageStat

options = set(sys.argv[5:])
if len(sys.argv) < 5 or options - {"--trim-transparent", "--upscale", "--invert-dark", "--boost-wide", "--best-logo"}:
    print("usage: png-to-lcd.py <input.png> <output.bin> <max_width> <max_height> [--trim-transparent] [--upscale] [--invert-dark] [--boost-wide] [--best-logo]")
    sys.exit(1)

infile, outfile, max_width, max_height = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
trim_transparent = "--trim-transparent" in options
allow_upscale = "--upscale" in options
invert_dark = "--invert-dark" in options
boost_wide = "--boost-wide" in options
best_logo = "--best-logo" in options

img = Image.open(infile)

# Real bug found via direct testing: a transparent PNG (the normal case
# for a real logo file -- confirmed by reproducing with a synthetic
# transparent-background test image) rendered as a SOLID BLACK BOX,
# completely swallowing the actual logo shape. PIL's own RGBA->L
# conversion silently drops the alpha channel and keeps whatever RGB
# value a transparent pixel happens to carry -- for freshly-created
# transparent pixels that's (0,0,0), i.e. black, not the white/
# background look you'd actually want. Compositing onto a real white
# background FIRST (only when there's an alpha channel to composite)
# makes transparent areas become background, same as "LIVE" would look
# on a real poster of this logo.
has_alpha = (
    img.mode in ("RGBA", "LA")
    or (img.mode == "P" and "transparency" in img.info)
    or "transparency" in img.info
)
colorful_logo = False
plaque_logo = False
if has_alpha:
    img = img.convert("RGBA")
    alpha = img.getchannel("A")
    alpha_has_transparency = alpha.getextrema()[0] < 255
    if trim_transparent:
        visible_bounds = alpha.getbbox()
        if not visible_bounds:
            raise ValueError(f"{infile} contains no visible pixels")
        img = img.crop(visible_bounds)
        alpha = img.getchannel("A")
    visible_rgb = img.convert("RGB")
    visible_luminance = visible_rgb.convert("L")
    visible_saturation = visible_rgb.convert("HSV").getchannel("S")
    colorful_logo = (
        best_logo
        and ImageStat.Stat(visible_saturation, mask=alpha).mean[0] >= 45
    )
    visible_pixels = [
        value for value, opacity in zip(visible_luminance.tobytes(), alpha.tobytes())
        if opacity > 128
    ]
    light_share = (
        sum(value > 200 for value in visible_pixels) / len(visible_pixels)
        if visible_pixels else 0
    )
    filled_share = ImageStat.Stat(alpha.point(lambda p: 255 if p > 128 else 0)).mean[0] / 255
    plaque_logo = colorful_logo and alpha_has_transparency and filled_share > 0.6
    if plaque_logo:
        # A badge that fills most of its area would become a solid block as
        # a silhouette, so keep its inner lettering: dark badge, light
        # artwork, and white outside the badge shape.
        inside = alpha.point(lambda p: 255 if p > 128 else 0)
        badge = Image.alpha_composite(Image.new("RGBA", img.size, (0, 0, 0, 255)), img)
        luminance = badge.convert("L")
        img = Image.composite(luminance, Image.new("L", img.size, 255), inside).convert("RGBA")
        alpha = Image.new("L", img.size, 255)
    elif colorful_logo and alpha_has_transparency and light_share > 0.6:
        # Mostly light lettering would vanish on the white background, so
        # use the alpha shape of such a multicolor mark instead.
        img = Image.new("RGBA", img.size, (0, 0, 0, 0))
        img.putalpha(alpha)
    # Invert bright, nearly monochrome artwork (such as white wordmarks).
    if (not colorful_logo
            and ImageStat.Stat(visible_luminance, mask=alpha).mean[0] > 127
            and ImageStat.Stat(visible_saturation, mask=alpha).mean[0] < 45):
        artwork = ImageOps.invert(img.convert("RGB"))
        artwork.putalpha(alpha)
        img = artwork
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    img = Image.alpha_composite(bg, img)
elif best_logo and img.mode in ("RGB", "P"):
    colorful_logo = (
        ImageStat.Stat(img.convert("RGB").convert("HSV").getchannel("S")).mean[0] >= 45
    )

img = img.convert("L")  # grayscale
if (invert_dark and not has_alpha and not (best_logo and colorful_logo)
        and ImageStat.Stat(img).mean[0] < 127):
    img = ImageOps.invert(img)
w, h = img.size
source_aspect = w / h
# Fit within max_width x max_height. Upscaling is opt-in so imported
# custom images keep their previous behavior; Steam game logos use it
# to make small marks more legible on the 160 x 43 LCD.
ratio = min(max_width / w, max_height / h)
if not allow_upscale:
    ratio = min(ratio, 1.0)
if ratio != 1.0:
    resample = Image.Resampling.LANCZOS
    img = img.resize((max(1, int(w * ratio)), max(1, int(h * ratio))), resample)
    w, h = img.size
if boost_wide and source_aspect > 5.5 and w == max_width and h < max_height:
    target_height = min(max_height - 2, max(h + 1, round(h * 1.25)))
    img = img.resize((w, target_height), Image.Resampling.LANCZOS)
    w, h = img.size

# Real quality issue found via direct A/B comparison on a simple
# two-tone test shape: the default Floyd-Steinberg dither (img.convert
# ("1") with no args) is the right call for a photo, but for a flat-
# color logo -- the only kind of image this project's own docs now
# tell you to expect, e.g. "an AMD logo" -- it turns clean mid-tone
# fills into visible speckle noise instead of a crisp edge. Stretching
# the tonal range first (autocontrast) then using a plain threshold
# (no error-diffusion) gives simple logos sharp, clean edges; it's a
# worse choice for an actual photograph, but this project's own README
# now explicitly scopes imports to simple high-contrast graphics, not
# photos, so this is the right default for what's actually supported.
img = ImageOps.autocontrast(img)
if best_logo:
    gray = img.convert("L")
    pixels = gray.tobytes()
    pixel_count = len(pixels)
    threshold_candidates = range(48, 225, 8)
    best_score = float("inf")
    best_threshold = 128
    for threshold in threshold_candidates:
        black = bytearray(1 if value < threshold else 0 for value in pixels)
        density = sum(black) / pixel_count
        transitions = 0
        isolated = 0
        for y in range(h):
            row = y * w
            for x in range(w):
                index = row + x
                if not black[index]:
                    continue
                neighbors = 0
                for dy in (-1, 0, 1):
                    ny = y + dy
                    if ny < 0 or ny >= h:
                        continue
                    for dx in (-1, 0, 1):
                        nx = x + dx
                        if (dx == 0 and dy == 0) or nx < 0 or nx >= w:
                            continue
                        if black[ny * w + nx]:
                            neighbors += 1
                if neighbors <= 1:
                    isolated += 1
                if x + 1 < w and black[index] != black[index + 1]:
                    transitions += 1
                if y + 1 < h and black[index] != black[index + w]:
                    transitions += 1
        edge_density = transitions / pixel_count
        target_density = 0.5 if plaque_logo else (0.22 if colorful_logo else 0.28)
        score = (abs(density - target_density)
                 + isolated / pixel_count * 0.7
                 + max(0.0, edge_density - 0.42) * 0.3)
        if score < best_score:
            best_score = score
            best_threshold = threshold
    def select_ink(pixels, w, h):
        pixel_count = w * h
        selected = bytearray(1 if value < best_threshold else 0 for value in pixels)
        visited = bytearray(pixel_count)
        for index in range(pixel_count):
            if not selected[index] or visited[index]:
                continue
            component = []
            pending = [index]
            visited[index] = 1
            while pending:
                current = pending.pop()
                component.append(current)
                x = current % w
                y = current // w
                for dy in (-1, 0, 1):
                    ny = y + dy
                    if ny < 0 or ny >= h:
                        continue
                    for dx in (-1, 0, 1):
                        nx = x + dx
                        if (dx == 0 and dy == 0) or nx < 0 or nx >= w:
                            continue
                        neighbor = ny * w + nx
                        if selected[neighbor] and not visited[neighbor]:
                            visited[neighbor] = 1
                            pending.append(neighbor)
            if len(component) <= 2:
                for pixel in component:
                    selected[pixel] = 0
        return selected

    selected = select_ink(pixels, w, h)
    # Fill the whole box: crop to the visible ink and scale it up so the
    # logo uses the full width or height, whatever padding the artwork has.
    xs = [i % w for i in range(pixel_count) if selected[i]]
    ys = [i // w for i in range(pixel_count) if selected[i]]
    if xs:
        left, right, top, bottom = min(xs), max(xs) + 1, min(ys), max(ys) + 1
        bw, bh = right - left, bottom - top
        fit = min(max_width / bw, max_height / bh)
        if (bw, bh) != (w, h) and fit > 1.0:
            gray = gray.crop((left, top, right, bottom))
            nw, nh = max(1, min(max_width, round(bw * fit))), max(1, min(max_height, round(bh * fit)))
            gray = gray.resize((nw, nh), Image.Resampling.LANCZOS)
            w, h = nw, nh
            pixels = gray.tobytes()
            pixel_count = w * h
            selected = select_ink(pixels, w, h)
    bitmap = bytes(0 if pixel else 255 for pixel in selected)
    img = Image.frombytes("L", (w, h), bitmap).convert("1")
else:
    img = img.point(lambda p: 255 if p > 128 else 0).convert("1")
if boost_wide and source_aspect > 5.5 and not best_logo:
    source = img.convert("L").tobytes()
    expanded = bytearray([255] * (w * (h + 2)))
    for y in range(h):
        row = source[y * w:(y + 1) * w]
        for dy in range(3):
            start = (y + dy) * w
            for x, pixel in enumerate(row):
                if pixel < expanded[start + x]:
                    expanded[start + x] = pixel
    img = Image.frombytes("L", (w, h + 2), bytes(expanded)).convert("1")
    h += 2

# Pillow's XBM save writes a C-style file (#define + byte array) --
# extract just the raw bytes from it. A unique temp filename (not a
# fixed path) avoids two conversions racing each other -- a real risk
# here: the GUI runs this both for a fresh import AND, on a background
# thread, every time you drag an image's resize handle, so two could
# genuinely overlap.
with tempfile.NamedTemporaryFile(suffix=".xbm", delete=False) as tmp:
    tmp_path = tmp.name
try:
    img.save(tmp_path, "XBM")
    with open(tmp_path) as f:
        xbm_src = f.read()
finally:
    os.unlink(tmp_path)

hex_bytes = re.findall(r"0x([0-9A-Fa-f]{2})", xbm_src)
# Real bug found via direct testing: Pillow's XBM writer encodes bit=1
# for a WHITE pixel (confirmed by comparing the raw bytes against a
# hand-computed expectation, byte-for-byte identical) -- but
# g15r_drawXBM (libg15render) draws bit=1 as BLACK. The two disagree,
# so every imported image rendered as a photo negative: confirmed by
# rendering a plain black circle on white through the real C binary
# and getting a solid dark box with a light HOLE where the circle
# should be. Inverting every byte here makes our .bin format match
# what g15r_drawXBM actually expects.
raw = bytes((~int(h, 16)) & 0xFF for h in hex_bytes)

with open(outfile, "wb") as f:
    f.write(raw)

print(f"{w} {h}")
