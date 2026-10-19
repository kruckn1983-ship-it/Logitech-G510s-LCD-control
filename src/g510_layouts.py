"""LCD geometry, sensor metadata and pure layout presets (no Qt or I/O)."""

LCD_WIDTH = 160

LCD_HEIGHT = 43

DEFAULT_SCREEN_PRESETS = {
    "L2": "system",
    "L3": "media",
    "L4": "temperatures",
    "L5": "network",
}

SCREEN_NAMES = {
    "L1": "Uhr", "L2": "System", "L3": "Media Center",
    "L4": "Spiele", "L5": "Netzwerk",
}

PRESET_NAMES = {
    "performance": "CPU-/GPU-Auslastung",
    "temperatures": "Temperaturübersicht",
    "system": "Systemübersicht",
    "network": "Netzwerkverbindung & Datenraten",
    "media": "Medienwiedergabe",
}

CPU_CORE_SENSOR_COUNT = 20

MAX_SENSOR_ELEMENTS = 32

GAME_BOUNDS_BASE = MAX_SENSOR_ELEMENTS

def build_layout_preset(preset):
    """Liefert die Elementliste einer Dashboard-Vorlage."""
    def sensor(key, x, y, style="number", width=40, orientation="horizontal",
               height=28, font_size=0):
        element = {
            "kind": "sensor", "sensor": key, "style": style,
            "orientation": orientation, "x": x, "y": y,
            "width": width, "height": height, "font_size": font_size,
        }
        if key in DATETIME_FORMAT_DEFAULTS:
            element["format"] = DATETIME_FORMAT_DEFAULTS[key]
        return element

    if preset == "performance":
        elements = [
            sensor(f"CPU_CORE_{core}", core * 10, 11, "bar", 8, "vertical", 29)
            for core in range(8)
        ]
        elements.extend([
            {**sensor("GPU_EDGE_TEMP", 82, 1), "label": "GPU"},
            {**sensor("GPU_PCT", 82, 14, "bar", 28), "label": "GPU"},
            {**sensor("RAM_PCT", 82, 29, "bar", 28), "label": "RAM"},
            {"kind": "text", "content": "CPU", "x": 0, "y": 1, "font_size": 0},
        ])
    elif preset == "temperatures":
        elements = [
            {**sensor("CPU_TEMP", 2, 2, font_size=1), "label": "CPU"},
            {**sensor("GPU_EDGE_TEMP", 82, 2, font_size=1), "label": "GPU"},
            {**sensor("MAXTEMP", 2, 17, font_size=1), "label": "MAX"},
            {**sensor("GPU_HOTSPOT_TEMP", 82, 17, font_size=1), "label": "HOT"},
            {**sensor("GPU_VRAM_TEMP", 2, 32, font_size=1), "label": "VRAM"},
        ]
    elif preset == "network":
        elements = [
            sensor("NET_CONNECTION", 0, 0),
            {**sensor("NET_DOWN", 2, 10, font_size=2), "label": "DL:", "max_width": 100},
            {**sensor("NET_UP", 2, 22, font_size=2), "label": "UL:", "max_width": 100},
            sensor("NET_IPV4", 2, 33),
            sensor("NET_DOWN", 110, 10, "history", width=48, height=10),
            sensor("NET_UP", 110, 22, "history", width=48, height=10),
        ]
    elif preset == "media":
        elements = [
            sensor("MEDIA_TITLE", 2, 1, font_size=1),
            sensor("MEDIA_ARTIST", 2, 11, font_size=0),
            sensor("MEDIA_ELAPSED", 2, 20, "bar", 65, font_size=0),
            {"kind": "visualizer", "x": 0, "y": 29,
             "width": LCD_WIDTH, "height": 14},
        ]
    elif preset == "system":
        elements = [
            {"kind": "frame", "x": x, "y": y, "width": w, "height": h}
            for x, y, w, h in ((0, 0, 82, 43), (0, 9, 82, 34),
                               (82, 0, 23, 43), (82, 9, 23, 10),
                               (105, 0, 55, 20), (105, 20, 55, 23))
        ]
        elements.extend([
            {"kind": "text", "content": "CPU", "x": 2, "y": 2, "font_size": 0},
            {**sensor("CPU_TEMP", 60, 2), "hide_label": 1, "max_width": 20},
            {"kind": "text", "content": "GPU", "x": 84, "y": 2, "font_size": 0},
            {**sensor("GPU_EDGE_TEMP", 84, 11), "hide_label": 1, "max_width": 19},
            {"kind": "text", "content": "MEM", "x": 108, "y": 2, "font_size": 0},
            {**sensor("TIME", 124, 2), "hide_label": 1, "max_width": 34},
            sensor("RAM_PCT", 108, 11, "gauge", width=49, height=7),
            {**sensor("NET_UP", 108, 23), "label": "UP", "max_width": 50, "format": "compact"},
            {**sensor("NET_DOWN", 108, 33), "label": "DN", "max_width": 50, "format": "compact"},
        ])
        elements.extend(
            {**sensor(f"CPU_CORE_{core}", 2 + core * 4, 11, "bar", 3,
                      "vertical", 30), "hide_label": 1}
            for core in range(CPU_CORE_SENSOR_COUNT)
        )
        elements.extend(
            {**sensor(key, 84 + i * 7, 21, "bar", 5, "vertical", 20),
             "hide_label": 1}
            for i, key in enumerate(("GPU_PCT", "VRAM_PCT", "GPU_EDGE_TEMP"))
        )
    else:
        elements = [
            sensor("TIME", 2, 0, font_size=2),
            {**sensor("DATE", 100, 1, font_size=1), "format": "eu"},
            {**sensor("CPU_TEMP", 2, 15, font_size=2), "label": "CPU"},
            {**sensor("GPU_EDGE_TEMP", 82, 15, font_size=2), "label": "GPU"},
            sensor("CPU_PCT", 2, 33, font_size=1),
            sensor("RAM_PCT", 55, 33, font_size=1),
            sensor("VRAM_PCT", 108, 33, font_size=1),
        ]
    return elements

SENSOR_CHOICES = [
    ("CPU_PCT", "CPU %"),
    *[(f"CPU_CORE_{i}", f"CPU-Thread {i + 1} %") for i in range(CPU_CORE_SENSOR_COUNT)],
    ("CPU_GHZ", "CPU GHz"),
    ("CPU_TEMP", "CPU-Temperatur"),
    ("RAM_PCT", "RAM %"),
    ("RAM_AMOUNT", "RAM belegt (Menge)"),
    ("VRAM_PCT", "VRAM %"),
    ("VRAM_AMOUNT", "VRAM belegt (Menge)"),
    ("MAXTEMP", "Höchste Temperatur"),
    ("GPU_PCT", "GPU %"),
    ("GPU_EDGE_TEMP", "GPU-Edge-Temperatur"),
    ("GPU_HOTSPOT_TEMP", "GPU-Hotspot-Temperatur"),
    ("GPU_VRAM_TEMP", "GPU-VRAM-Temperatur"),
    ("SWAP_PCT", "Swap %"),
    ("DISK_ROOT_PCT", "Datenträger % (Root)"),
    ("DISK_SECONDARY_PCT", "Datenträger % (sekundär)"),
    ("UPTIME", "Laufzeit"),
    ("NET_DOWN", "Netzwerk-Downloadrate"),
    ("NET_UP", "Netzwerk-Uploadrate"),
    ("NET_CONNECTION", "Netzwerk: aktive Verbindung"),
    ("NET_IPV4", "Netzwerk: lokale IPv4-Adresse"),
    ("TIME", "Uhrzeit"),
    ("DATE", "Datum"),
    ("MEDIA_TITLE", "Medien: Titel"),
    ("MEDIA_ARTIST", "Medien: Interpret"),
    ("MEDIA_ELAPSED", "Medien: Spielzeit"),
    ("MB_TEMP1", "Mainboard-Temperatur 1 (unbeschriftet)"),
    ("MB_TEMP2", "Mainboard-Temperatur 2 (unbeschriftet)"),
    ("MB_TEMP3", "Mainboard-Temperatur 3 (unbeschriftet)"),
    ("MB_TEMP4", "Mainboard-Temperatur 4 (unbeschriftet)"),
    ("MB_TEMP5", "Mainboard-Temperatur 5 (unbeschriftet)"),
    ("MB_TEMP6", "Mainboard-Temperatur 6 (unbeschriftet)"),
]

SENSOR_LABELS = dict(SENSOR_CHOICES)

DEFAULT_SENSOR_DISPLAY_LABELS = {
    "CPU_PCT": "CPU",
    **{f"CPU_CORE_{i}": f"C{i + 1}" for i in range(CPU_CORE_SENSOR_COUNT)},
    "CPU_GHZ": "GHZ",
    "CPU_TEMP": "CPU",
    "RAM_PCT": "RAM",
    "RAM_AMOUNT": "AMT",
    "VRAM_PCT": "VRAM",
    "VRAM_AMOUNT": "AMT",
    "MAXTEMP": "MAXT",
    "GPU_PCT": "GPU",
    "GPU_EDGE_TEMP": "GPU",
    "GPU_HOTSPOT_TEMP": "HOT",
    "GPU_VRAM_TEMP": "VMEM",
    "SWAP_PCT": "SWAP",
    "DISK_ROOT_PCT": "DISK",
    "DISK_SECONDARY_PCT": "DSK2",
    "UPTIME": "UPTM",
    "NET_DOWN": "DN",
    "NET_UP": "UP",
    "NET_CONNECTION": "",
    "NET_IPV4": "IP:",
    "TIME": "",
    "DATE": "",
    "MEDIA_TITLE": "",
    "MEDIA_ARTIST": "",
    "MEDIA_ELAPSED": "",
    **{f"MB_TEMP{i}": f"MB{i}" for i in range(1, 7)},
}

DATETIME_FORMAT_CHOICES = {
    "TIME": [
        ("hms", "24-Stunden HH:MM:SS"),
        ("hm", "24-Stunden HH:MM"),
        ("ampm", "12-Stunden HH:MM AM/PM"),
    ],
    "DATE": [
        ("short", "TT Mon"),
        ("eu", "TT.MM.JJJJ"),
        ("eu_short", "TT.MM."),
        ("iso", "JJJJ-MM-TT"),
    ],
}

DATETIME_FORMAT_DEFAULTS = {"TIME": "hms", "DATE": "short"}

SENSOR_DESCRIPTIONS = {
    "CPU_PCT": "Gesamte CPU-Auslastung, gemittelt über alle Kerne.",
    **{f"CPU_CORE_{i}": f"Auslastung des logischen CPU-Threads {i + 1}."
       for i in range(CPU_CORE_SENSOR_COUNT)},
    "CPU_GHZ": "Aktuelle CPU-Taktfrequenz.",
    "CPU_TEMP": "CPU-Package-Temperatur.",
    "RAM_PCT": "Belegter RAM in Prozent des Gesamtspeichers.",
    "RAM_AMOUNT": "Belegter RAM als konkrete Menge (z. B. 12,3 GB).",
    "VRAM_PCT": "Belegter GPU-VRAM in Prozent des Gesamtspeichers.",
    "VRAM_AMOUNT": "Belegter GPU-VRAM als konkrete Menge.",
    "MAXTEMP": "Höchste CPU-Temperatur seit dem letzten Start des LCD-Dienstes – kein Allzeitrekord.",
    "GPU_PCT": "GPU-Auslastung.",
    "GPU_EDGE_TEMP": "Der Haupt-Temperatursensor des GPU-Chips – das, was die meisten Tools einfach „GPU-Temperatur“ nennen.",
    "GPU_HOTSPOT_TEMP": "Der heißeste Punkt auf dem GPU-Chip – meist etwas höher als die Edge-Temperatur.",
    "GPU_VRAM_TEMP": "Temperatur des GPU-Speichers (VRAM) – getrennt vom GPU-Chip selbst.",
    "SWAP_PCT": "Belegter Swap-Speicher in Prozent des gesamten Swaps.",
    "DISK_ROOT_PCT": "Belegter Speicherplatz im Root-Dateisystem (/).",
    "DISK_SECONDARY_PCT": "Belegter Speicherplatz auf einem optionalen zweiten Laufwerk, falls eingerichtet.",
    "UPTIME": "Wie lange dieser PC seit dem Start läuft.",
    "NET_DOWN": "Aktuelle Download-Geschwindigkeit im Netzwerk.",
    "NET_UP": "Aktuelle Upload-Geschwindigkeit im Netzwerk.",
    "NET_CONNECTION": "Aktive Schnittstelle mit Link-Status; kein Nachweis einer Internetverbindung.",
    "NET_IPV4": "Lokale IPv4-Adresse der ausgewählten Schnittstelle, nicht die öffentliche IP.",
    "TIME": "Aktuelle Uhrzeit (dieselbe Uhr wie auf dem Uhrbildschirm).",
    "DATE": "Aktuelles Datum (dasselbe Datum wie auf dem Uhrbildschirm).",
    "MEDIA_TITLE": "Titel des aktuell gespielten Songs über einen MPRIS-kompatiblen Player (Spotify, Browser-Tabs, VLC usw.). Leer, wenn nichts läuft.",
    "MEDIA_ARTIST": "Aktuell gespielter Interpret, gleiche Quelle wie Medien: Titel.",
    "MEDIA_ELAPSED": "Wiedergabeposition und Dauer. Der Balkenstil zeigt den Titelfortschritt bei Medien mit bekannter Dauer.",
    **{f"MB_TEMP{i}": "Einer der Temperatursensoren deines Mainboards – die Hardware gibt nicht an, was er misst." for i in range(1, 7)},
}

# Matches the renderer's percent, 0-90C temperature and playback-progress scales.
BAR_CAPABLE_SENSORS = {
    "CPU_PCT", *{f"CPU_CORE_{i}" for i in range(CPU_CORE_SENSOR_COUNT)},
    "CPU_TEMP", "RAM_PCT", "VRAM_PCT", "MAXTEMP",
    "GPU_PCT", "GPU_EDGE_TEMP", "GPU_HOTSPOT_TEMP", "GPU_VRAM_TEMP",
    "SWAP_PCT", "DISK_ROOT_PCT", "DISK_SECONDARY_PCT",
    "MEDIA_ELAPSED",
    "MB_TEMP1", "MB_TEMP2", "MB_TEMP3", "MB_TEMP4", "MB_TEMP5", "MB_TEMP6",
}

# Old configurations remain readable after the sensor rename.
LEGACY_SENSOR_ALIASES = {"DISK_FRIGIDER_PCT": "DISK_SECONDARY_PCT"}

CUSTOM_SCREEN_KEYS = ["L2", "L3", "L4", "L5"]

MAX_IMAGES_PER_SCREEN = 2  # matches MAX_IMAGES in g510_lcd_stats.c

MAX_TEXTS_PER_SCREEN = 4  # matches MAX_TEXTS in g510_lcd_stats.c

MAX_VISUALIZERS_PER_SCREEN = 1  # matches MAX_VISUALIZERS in g510_lcd_stats.c -- only one persistent audio-capture stream exists process-wide, a second visualizer element would just duplicate the same bar data

DEFAULT_VISUALIZER_WIDTH = 70

DEFAULT_VISUALIZER_HEIGHT = 37

TEXT_CHAR_PX = 6  # rough estimate for G15_TEXT_SMALL's per-character width -- no real font-metric access from Python for freeform text (same reason sensor elements originally needed the .meta sidecar), but text elements deliberately skip that mechanism (see on_add_text's docstring) so this stays an approximation, not pixel-perfect

FONT_SIZE_CHOICES = [(0, "Klein"), (1, "Mittel"), (2, "Groß"), (3, "Riesig")]

MAX_BAR_FONT_SIZE = 1

FONT_SIZE_SCALE = {0: (1.0, 1.0), 1: (9 / 7, 6 / 5), 2: (15 / 7, 7 / 5), 3: (13 / 7, 10 / 5)}
