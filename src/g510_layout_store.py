"""Layout persistence; caller supplies paths and the screen catalog."""
import urllib.parse

from g510_layouts import (
    DATETIME_FORMAT_CHOICES, DATETIME_FORMAT_DEFAULTS, LEGACY_SENSOR_ALIASES,
)

GAME_DASHBOARD_COMPONENTS = ("logo", "cpu", "gpu")

def _encode_custom_screen_value(value):
    """Encode freeform values so whitespace and underscores round-trip
    through the LCD service's space-delimited config format."""
    return urllib.parse.quote(value, safe="-.~").replace("_", "%5F")

def _decode_custom_screen_value(value):
    return urllib.parse.unquote(value)

def load_game_dashboard_offsets(path):
    offsets = {component: {"x": 0, "y": 0} for component in GAME_DASHBOARD_COMPONENTS}
    if not path.exists():
        return offsets
    for token in path.read_text().split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        component, separator, axis = key.partition("_")
        if separator and component in offsets and axis in ("x", "y"):
            try:
                offsets[component][axis] = int(value)
            except ValueError:
                continue
    return offsets

def save_game_dashboard_offsets(offsets, path):
    lines = [
        f"{component}_{axis}={offsets[component][axis]}"
        for component in GAME_DASHBOARD_COMPONENTS
        for axis in ("x", "y")
    ]
    path.write_text(" ".join(lines) + "\n")

def load_custom_screens(path, screens):
    """Returns {"L2": [ {kind:"sensor",sensor,style,x,y,width} or
    {kind:"image",path,x,y,width,height}, ... ], "L3": [...], ...}"""
    config = {f"L{key}": [] for key in screens if key != 1}
    if not path.exists():
        return config
    current = None
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith("SCREEN "):
            key = line.split(" ", 1)[1]
            if key.startswith("L") and key[1:].isdecimal() and 2 <= int(key[1:]) <= 2147483647:
                config.setdefault(key, [])
                current = key
            else:
                current = None
        elif line.startswith("ELEMENT ") and current:
            el = {
                "kind": "sensor", "sensor": "", "style": "number",
                "orientation": "horizontal", "x": 0, "y": 0,
                "width": 40, "height": 28, "font_size": 0, "label": "", "format": "",
            }
            for tok in line[len("ELEMENT "):].split():
                if "=" not in tok:
                    continue
                k, v = tok.split("=", 1)
                if k in ("x", "y", "width", "height", "max_width", "hide_label"):
                    try:
                        el[k] = int(v)
                    except ValueError:
                        pass
                elif k == "font":
                    try:
                        el["font_size"] = int(v) if int(v) in (0, 1, 2, 3) else 0
                    except ValueError:
                        pass
                elif k in ("sensor", "style", "orientation"):
                    el[k] = v
                elif k == "label":
                    el[k] = v.replace("_", " ")
                elif k == "label2":
                    el["label"] = _decode_custom_screen_value(v)
                elif k == "format" and v in {"compact"} | {
                    choice for choices in DATETIME_FORMAT_CHOICES.values()
                    for choice, _ in choices
                }:
                    el[k] = v
            if el["sensor"]:
                el["sensor"] = LEGACY_SENSOR_ALIASES.get(el["sensor"], el["sensor"])
                config[current].append(el)
        elif line.startswith("IMAGE ") and current:
            # "src" is optional and only present for images imported
            # since drag-resize was added: a copy of the original
            # source picture (not the already-downscaled/dithered
            # .bin) kept alongside it so a resize can re-convert from
            # real source quality instead of upscaling a 1-bit bitmap.
            # Older IMAGE lines without src= parse fine -- src just
            # stays absent, and those images fall back to no resize
            # handle (same as today: re-import to change size).
            im = {"kind": "image", "path": "", "x": 0, "y": 0, "width": 0, "height": 0, "src": None}
            for tok in line[len("IMAGE "):].split():
                if "=" not in tok:
                    continue
                k, v = tok.split("=", 1)
                if k in ("x", "y", "width", "height"):
                    try:
                        im[k] = int(v)
                    except ValueError:
                        pass
                elif k in ("path", "src"):
                    im[k] = v
            if im["path"] and im["width"] > 0 and im["height"] > 0:
                config[current].append(im)
        elif line.startswith("TEXT ") and current:
            # Underscores decode to spaces -- matches g510_lcd_stats.c's
            # own decoding exactly, keeps the space-delimited line
            # parser on both sides simple (no quoted-string handling).
            tx = {"kind": "text", "content": "", "x": 0, "y": 0, "font_size": 0}
            for tok in line[len("TEXT "):].split():
                if "=" not in tok:
                    continue
                k, v = tok.split("=", 1)
                if k in ("x", "y"):
                    try:
                        tx[k] = int(v)
                    except ValueError:
                        pass
                elif k == "font":
                    try:
                        tx["font_size"] = int(v) if int(v) in (0, 1, 2, 3) else 0
                    except ValueError:
                        pass
                elif k == "content":
                    tx[k] = v.replace("_", " ")
                elif k == "content2":
                    tx["content"] = _decode_custom_screen_value(v)
            if tx["content"]:
                config[current].append(tx)
        elif line.startswith(("VISUALIZER ", "FRAME ")) and current:
            prefix, rest = line.split(" ", 1)
            vz = {"kind": "frame" if prefix == "FRAME" else "visualizer",
                  "x": 0, "y": 0, "width": 0, "height": 0}
            for tok in rest.split():
                if "=" not in tok:
                    continue
                k, v = tok.split("=", 1)
                if k in ("x", "y", "width", "height"):
                    try:
                        vz[k] = int(v)
                    except ValueError:
                        pass
            if vz["width"] > 0 and vz["height"] > 0:
                config[current].append(vz)
    return config

def save_custom_screens(config, path):
    lines = []
    for key in config:
        lines.append(f"SCREEN {key}")
        for el in config[key]:
            if el.get("kind") == "image":
                src_part = f" src={el['src']}" if el.get("src") else ""
                lines.append(
                    f"IMAGE path={el['path']} width={el['width']} height={el['height']} "
                    f"x={el['x']} y={el['y']}{src_part}"
                )
            elif el.get("kind") == "text":
                content = _encode_custom_screen_value(el["content"]) or "%20"
                lines.append(f"TEXT content2={content} x={el['x']} y={el['y']} font={el.get('font_size', 0)}")
            elif el.get("kind") in ("visualizer", "frame"):
                prefix = "FRAME" if el["kind"] == "frame" else "VISUALIZER"
                lines.append(f"{prefix} x={el['x']} y={el['y']} width={el['width']} height={el['height']}")
            else:
                width = el.get("width", 40)
                orientation = el.get("orientation", "horizontal")
                line = (
                    f"ELEMENT sensor={el['sensor']} style={el['style']} "
                    f"x={el['x']} y={el['y']} width={width} font={el.get('font_size', 0)}"
                )
                if el.get("label"):
                    line += f" label2={_encode_custom_screen_value(el['label'])}"
                if el.get("sensor") in DATETIME_FORMAT_CHOICES:
                    date_format = el.get("format") or DATETIME_FORMAT_DEFAULTS[el["sensor"]]
                    line += f" format={date_format}"
                elif el.get("sensor") in ("NET_UP", "NET_DOWN") and el.get("format") == "compact":
                    line += " format=compact"
                if orientation == "vertical" and el.get("style") == "bar":
                    line += f" orientation=vertical height={el.get('height', 28)}"
                if el.get("style") in ("history", "gauge"):
                    line += f" height={el.get('height', 10)}"
                if el.get("max_width", 0) > 0:
                    line += f" max_width={el['max_width']}"
                if el.get("hide_label"):
                    line += " hide_label=1"
                lines.append(line)
    temporary = path.with_suffix(".tmp")
    temporary.write_text("\n".join(lines) + "\n")
    temporary.replace(path)
