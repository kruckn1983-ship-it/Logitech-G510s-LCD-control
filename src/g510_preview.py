"""One-shot native LCD rendering and its image/bounds protocol."""
from pathlib import Path
import subprocess

from PyQt5.QtGui import QImage, QPixmap

def _parse_bounds_meta(meta_path):
    """Parses the .meta sidecar --preview writes alongside the image for
    custom screens: real per-element pixel bounds computed with the
    label font's actual glyph metrics, which Python has no way to
    compute itself. Returns {index: {"label_x1":.., ..., "bar_x1":.. (bar
    elements only)}}. Missing/unreadable file -> empty dict, callers
    fall back to an approximation rather than crashing."""
    bounds = {}
    try:
        text = meta_path.read_text()
    except Exception:
        return bounds
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        try:
            idx = int(parts[0])
        except ValueError:
            continue
        entry = {}
        for tok in parts[1:]:
            if "=" not in tok:
                continue
            k, v = tok.split("=", 1)
            try:
                entry[k] = int(v)
            except ValueError:
                pass
        bounds[idx] = entry
    return bounds

def render_preview(binary, screen_num, tag="app", editor=False):
    """Runs the same C binary that draws the real LCD, in one-shot
    --preview mode, and returns (QPixmap, bounds, err) -- the pixmap is
    uses the same drawing code as the real screen. With editor=True,
    the automatic L4 game dashboard also reports hitboxes for its
    logo and temperature blocks, making those items draggable.
    bounds is real per-element pixel geometry (see _parse_bounds_meta),
    empty dict for non-custom screens or if the sidecar wasn't written.

    `tag` picks the output file so independent callers (the Custom
    Screens editor's own live preview, the canvas's LCD-mirror
    thumbnail) never race on the same /tmp file -- two callers hitting
    this at once with the same tag could still interleave a partial
    read; distinct tags avoid that entirely rather than relying on
    both finishing fast enough not to matter."""
    if not binary.exists():
        return None, {}, "Noch nicht gebaut – führe install.sh aus oder baue die C-Programme neu."
    out_path = Path(f"/tmp/g510_app_preview_{tag}.ppm")
    meta_path = Path(str(out_path) + ".meta")
    try:
        result = subprocess.run(
            [
                str(binary),
                "--preview-editor" if editor else "--preview",
                str(screen_num),
                str(out_path),
            ],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None, {}, f"Vorschau-Rendering fehlgeschlagen: {result.stderr.strip()}"
    except Exception as e:
        return None, {}, f"Vorschau konnte nicht gestartet werden: {e}"

    try:
        data = out_path.read_bytes()
    except Exception as e:
        return None, {}, f"Vorschauausgabe konnte nicht gelesen werden: {e}"

    # Minimal hand-rolled P6 PPM parser -- avoids depending on Qt's
    # optional ppm plugin being present on whatever system this runs on.
    if not data.startswith(b"P6"):
        return None, {}, "Die Vorschauausgabe war kein gültiges PPM-Bild."
    parts = data.split(b"\n", 3)
    if len(parts) < 4:
        return None, {}, "Ungültiger PPM-Header."
    try:
        w, h = (int(x) for x in parts[1].split())
    except ValueError:
        return None, {}, "Ungültiger PPM-Header."
    pixels = parts[3]
    img = QImage(w, h, QImage.Format_RGB888)
    if len(pixels) < w * h * 3:
        return None, {}, "PPM-Daten unvollständig."
    for y in range(h):
        row_start = y * w * 3
        img.scanLine(y)  # ensure detach
        for x in range(w):
            i = row_start + x * 3
            img.setPixel(x, y, (pixels[i] << 16) | (pixels[i + 1] << 8) | pixels[i + 2])
    bounds = _parse_bounds_meta(meta_path)
    return QPixmap.fromImage(img), bounds, None
