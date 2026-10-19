"""Screen-dependent LCD key actions. No shell commands or arbitrary bindings."""
import json
import os
from pathlib import Path
import subprocess
import sys


SCREENS = {2: "System", 3: "Media Center", 4: "Spiele", 5: "Netzwerk", 1: "Uhr"}
SCREEN_ORDER = tuple(SCREENS)
CLOCK_LAYOUTS = (
    "Digital pur", "Panorama", "Dashboard", "Zeitkacheln", "Siebensegment",
    "Kontur", "Nachtmodus", "Analog links", "Analog rechts", "Zifferblatt",
    "Binäruhr", "Zeitspalten", "Gestapelt", "Sekundenlauf", "Kalender",
    "Klappzahlen", "Punktmatrix", "Rahmenlos", "Terminal", "Tagesfortschritt",
)
CLOCK_ACTIONS = {"clock_previous": "Uhr-Layout zurück", "clock_next": "Uhr-Layout weiter"}
ACTIONS = {
    "none": "Keine Aktion",
    "previous": "Vorheriger Titel",
    "next": "Nächster Titel",
    "play": "Play",
    "pause": "Pause",
    "play_pause": "Play / Pause",
    "volume_down": "Lautstärke −",
    "volume_up": "Lautstärke +",
    "mute": "Stumm umschalten",
    **CLOCK_ACTIONS,
    **{f"screen_{key}": f"Bildschirm: {name}" for key, name in SCREENS.items()},
}
CONFIG_PATH = Path.home() / ".local/share/g510-lcd/lcd_keys.json"
SCREENS_PATH = CONFIG_PATH.with_name("screens.json")
CLOCK_LAYOUT_PATH = CONFIG_PATH.with_name("clock_layout")


def load_clock_layout():
    try:
        value = CLOCK_LAYOUT_PATH.read_text().strip()
    except FileNotFoundError:
        return 0
    if not value.isascii() or not value.isdecimal() or not 0 <= int(value) < len(CLOCK_LAYOUTS):
        raise ValueError("Ungültiges Uhr-Layout (erwartet: 0 bis 19)")
    return int(value)


def save_clock_layout(index):
    if type(index) is not int or not 0 <= index < len(CLOCK_LAYOUTS):
        raise ValueError("Unbekanntes Uhr-Layout")
    CLOCK_LAYOUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = CLOCK_LAYOUT_PATH.with_suffix(".tmp")
    temporary.write_text(f"{index}\n")
    temporary.replace(CLOCK_LAYOUT_PATH)


def load_screen_catalog():
    try:
        data = json.loads(SCREENS_PATH.read_text())
    except FileNotFoundError:
        return {"next_id": 6, "screens": []}
    if (not isinstance(data, dict) or not isinstance(data.get("screens"), list)
            or type(data.get("next_id")) is not int):
        raise ValueError("Ungültiger Bildschirmkatalog")
    ids = set(SCREENS)
    names = {name.casefold() for name in SCREENS.values()}
    for entry in data["screens"]:
        if (not isinstance(entry, dict) or type(entry.get("id")) is not int
                or not 6 <= entry["id"] <= 2147483647 or entry["id"] in ids
                or not isinstance(entry.get("name"), str)
                or not entry["name"].strip()
                or any(ord(c) < 32 for c in entry["name"])
                or entry["name"].casefold() in names):
            raise ValueError("Ungültiger oder doppelter eigener Bildschirm")
        ids.add(entry["id"])
        names.add(entry["name"].casefold())
    if not max(ids) < data["next_id"] <= 2147483648:
        raise ValueError("Ungültige nächste Bildschirm-ID")
    return data


def load_screens():
    return {**SCREENS, **{entry["id"]: entry["name"]
                         for entry in load_screen_catalog()["screens"]}}


def save_screen_catalog(data):
    write_json(data, SCREENS_PATH)


def action_labels():
    return {**ACTIONS, **{f"screen_{key}": f"Bildschirm: {name}"
                         for key, name in load_screens().items()}}


def default_bindings(screens=None):
    result = {str(screen): {f"L{key}": "none" for key in range(2, 6)}
              for screen in (load_screens() if screens is None else screens)}
    result["3"] = dict(zip(("L2", "L3", "L4", "L5"),
                          ("previous", "next", "play", "pause")))
    result["1"].update(L2="clock_previous", L3="clock_next")
    return result


def load_bindings(path=CONFIG_PATH):
    expected = default_bindings()
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return expected
    if not isinstance(data, dict) or not set(map(str, SCREENS)).issubset(data):
        raise ValueError("Ungültige Bildschirme in LCD-Tastenbelegung")
    actions = action_labels()
    for screen, bindings in data.items():
        if not screen.isdecimal() or int(screen) < 1:
            raise ValueError("Ungültige Bildschirm-ID in LCD-Tastenbelegung")
        if not isinstance(bindings, dict) or bindings.keys() != expected["2"].keys():
            raise ValueError(f"Ungültige Tasten für Bildschirm {screen}")
        for key, action in bindings.items():
            if not isinstance(action, str):
                raise ValueError(f"Unbekannte Aktion für Bildschirm {screen}")
            if action not in actions:
                if action.startswith("screen_") and action[7:].isdecimal():
                    action = "none"  # A deleted screen can no longer be a target.
                else:
                    raise ValueError(f"Unbekannte Aktion für Bildschirm {screen}")
            if screen in expected:
                expected[screen][key] = action
    return expected


def save_bindings(data, path=CONFIG_PATH):
    write_json(data, path)


def write_json(data, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def runtime_path(name):
    return Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / name


def read_screen():
    try:
        value = int(runtime_path("g510lcd_screen").read_text())
    except FileNotFoundError:
        return 2
    if value == 0:
        return 2  # Legacy statistics screen mirrors System.
    if value not in load_screens():
        raise ValueError(f"Ungültiger Bildschirm: {value}")
    return value


def show_screen(screen):
    if screen not in load_screens():
        raise ValueError(f"Unbekannter Bildschirm: {screen}")
    # Write the override before the new screen so auto-selection cannot undo it.
    runtime_path("g510lcd_manual_screen").write_text("1")
    destination = runtime_path("g510lcd_screen")
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(str(screen))
    temporary.replace(destination)


def next_screen(current):
    if current == 0:
        current = 2
    order = tuple(load_screens())
    if current not in order:
        raise ValueError(f"Unbekannter Bildschirm: {current}")
    return order[(order.index(current) + 1) % len(order)]


def select_player():
    result = subprocess.run(
        ["playerctl", "-a", "metadata", "--format",
         "{{playerInstance}}\x1f{{status}}"], capture_output=True, text=True,
        timeout=3, check=True)
    players = []
    for line in result.stdout.splitlines():
        name, separator, status = line.partition("\x1f")
        if separator and name and status in ("Playing", "Paused", "Stopped"):
            players.append((name, status))
    if not players:
        raise RuntimeError("Kein steuerbarer MPRIS-Player gefunden")
    return min(players, key=lambda item: (
        {"Playing": 0, "Paused": 1, "Stopped": 2}[item[1]],
        not item[0].startswith("plasma-browser-integration")))[0]


def perform_action(action):
    if action == "none":
        return
    if action in CLOCK_ACTIONS:
        if read_screen() != 1:
            raise ValueError("Uhr-Layouts können nur im aktiven Uhr-Screen gewechselt werden")
        step = 1 if action == "clock_next" else -1
        save_clock_layout((load_clock_layout() + step) % len(CLOCK_LAYOUTS))
        return
    if action.startswith("screen_") and action in action_labels():
        show_screen(int(action.removeprefix("screen_")))
        return
    media = {"previous": "previous", "next": "next", "play": "play",
             "pause": "pause", "play_pause": "play-pause"}
    if action in media:
        arguments = ["playerctl", "-p", select_player(), media[action]]
    elif action in ("volume_down", "volume_up", "mute"):
        arguments = {
            "volume_down": ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-5%"],
            "volume_up": ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%"],
            "mute": ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"],
        }[action]
    else:
        raise ValueError(f"Unbekannte Aktion: {action}")
    subprocess.run(arguments, timeout=3, check=True)


def handle_key(key):
    if key == "L1":
        show_screen(next_screen(read_screen()))
    elif key in ("L2", "L3", "L4", "L5"):
        perform_action(load_bindings()[str(read_screen())][key])
    else:
        raise ValueError(f"Unbekannte Taste: {key}")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("Aufruf: g510_screen_keys.py L1|L2|L3|L4|L5")
        handle_key(sys.argv[1])
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"g510-lcd-keys: {error}", file=sys.stderr)
        sys.exit(1)
