"""Per-game temporary backlight colors, independent of audio and the GUI."""
import json
import os
from pathlib import Path
import signal
import re
import subprocess
import sys

DATA_DIR = Path.home() / ".local/share/g510-lcd"
CONFIG_PATH = DATA_DIR / "game_colors.json"
LED_DIR = Path("/sys/class/leds/g15::kbd_backlight")


def load_standard_color(path=None):
    path = DATA_DIR / "set-backlight-color.sh" if path is None else path
    try:
        script = path.read_text()
    except FileNotFoundError:
        return None
    match = re.search(
        r'^\s*echo\s+["\']?(\d+)\s+(\d+)\s+(\d+)["\']?\s*>\s*'
        r'/sys/class/leds/g15::kbd_backlight/multi_intensity\s*$', script, re.MULTILINE)
    if not match or any(int(value) > 255 for value in match.groups()):
        raise ValueError("Die gespeicherte Standardfarbe ist ungültig.")
    return tuple(map(int, match.groups()))


def load_colors(path=None):
    path = CONFIG_PATH if path is None else path
    try:
        colors = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    if not isinstance(colors, dict):
        raise ValueError("Ungültige Spiele-Farbkonfiguration")
    for appid, rgb in colors.items():
        if (not appid.isascii() or not appid.isdecimal() or int(appid) <= 0
                or not isinstance(rgb, list) or len(rgb) != 3
                or any(type(value) is not int or not 0 <= value <= 255 for value in rgb)):
            raise ValueError(f"Ungültige Spielfarbe für {appid}")
    return colors


def save_color(appid, rgb, path=None):
    path = CONFIG_PATH if path is None else path
    if type(appid) is not int or appid <= 0:
        raise ValueError("Ungültige Steam-App-ID")
    colors = load_colors(path)
    if rgb is None:
        colors.pop(str(appid), None)
    else:
        if len(rgb) != 3 or any(type(v) is not int or not 0 <= v <= 255 for v in rgb):
            raise ValueError("Ungültiger RGB-Farbwert")
        colors[str(appid)] = list(rgb)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(colors, indent=2) + "\n")
    temporary.replace(path)


def process_games(proc=Path("/proc"), uid=None):
    """Steam exports these IDs to native games, Proton and their children."""
    uid = os.getuid() if uid is None else uid
    result = {}
    for entry in proc.iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            if entry.stat().st_uid != uid:
                continue
            environment = entry.joinpath("environ").read_bytes()
            status = entry.joinpath("status").read_text()
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError:
            # Same-user protected processes cannot be identified from /proc.
            continue
        for field in environment.split(b"\0"):
            key, _, value = field.partition(b"=")
            if key in (b"SteamAppId", b"STEAM_COMPAT_APP_ID", b"SteamGameId"):
                if value.isdigit() and 0 < int(value) < 100000000:
                    result[int(entry.name)] = int(value)
                    break
        # Ignore zombies; they no longer own a running game.
        if any(line.startswith("State:") and "Z" in line for line in status.splitlines()):
            result.pop(int(entry.name), None)
    return result


class ColorController:
    def __init__(self, apply, restore):
        self.apply = apply
        self.restore = restore
        self.owner = None
        self.color = None

    def update(self, colors, games, foreground_pid):
        running = set(games.values())
        focused = games.get(foreground_pid)
        target = focused if str(focused) in colors else self.owner
        if target not in running or str(target) not in colors:
            target = None
        rgb = tuple(colors[str(target)]) if target is not None else None
        if rgb is None:
            if self.owner is not None:
                self.restore()
            self.owner = self.color = None
        elif rgb != self.color or target != self.owner:
            self.apply(rgb)
            self.owner, self.color = target, rgb

    def close(self):
        if self.owner is not None:
            self.restore()
            self.owner = self.color = None


def apply_color(rgb):
    (LED_DIR / "multi_intensity").write_text(" ".join(map(str, rgb)))
    (LED_DIR / "brightness").write_text("255")


def restore_color():
    script = DATA_DIR / "set-backlight-color.sh"
    subprocess.run(["/bin/bash", "-e", str(script)], check=True, timeout=5)


def main():
    from PyQt5.QtCore import QCoreApplication, QObject, QTimer, pyqtSlot
    from PyQt5.QtDBus import QDBusConnection, QDBusMessage
    app = QCoreApplication(sys.argv)
    bus = QDBusConnection.sessionBus()
    service = "org.g510.GameColors"
    interface = "org.g510.GameColors"
    plugin = "g510-game-colors"

    class Foreground(QObject):
        pid = 0

        @pyqtSlot(int)
        def activated(self, pid):
            self.pid = pid

        @pyqtSlot(result=int)
        def currentPid(self):
            return self.pid

    foreground = Foreground()
    if not bus.registerService(service) or not bus.registerObject(
            "/Foreground", interface, foreground, QDBusConnection.ExportAllSlots):
        raise RuntimeError("Spiele-Farbdienst: D-Bus-Registrierung fehlgeschlagen")

    def kwin(method, arguments):
        message = QDBusMessage.createMethodCall(
            "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", method)
        message.setArguments(arguments)
        reply = bus.call(message)
        if reply.type() == QDBusMessage.ErrorMessage:
            raise RuntimeError(f"KWin-Fenstererkennung: {reply.errorMessage()}")
        return reply.arguments()

    use_kwin = bus.interface().isServiceRegistered("org.kde.KWin").value()
    script = None
    if use_kwin:
        runtime = Path(os.environ["XDG_RUNTIME_DIR"])
        script = runtime / "g510-game-colors.js"
        script.write_text(
            'function notify() {\n'
            ' var w = workspace.activeWindow || workspace.activeClient;\n'
            ' callDBus("org.g510.GameColors", "/Foreground", "org.g510.GameColors",'
            ' "activated", w ? w.pid : 0);\n'
            '}\n'
            'if (workspace.windowActivated) workspace.windowActivated.connect(notify);\n'
            'else workspace.clientActivated.connect(notify);\nnotify();\n')
        kwin("unloadScript", [plugin])
        identifier = kwin("loadScript", [str(script), plugin])[0]
        if identifier < 0:
            raise RuntimeError("KWin konnte die Vordergrunderkennung nicht laden")
        message = QDBusMessage.createMethodCall(
            "org.kde.KWin", f"/Scripting/Script{identifier}", "org.kde.kwin.Script", "run")
        reply = bus.call(message)
        if reply.type() == QDBusMessage.ErrorMessage:
            raise RuntimeError(reply.errorMessage())
    elif os.environ.get("XDG_SESSION_TYPE") == "wayland":
        raise RuntimeError("Spielfarben: Wayland-Vordergrunderkennung benötigt KDE/KWin.")

    controller = ColorController(apply_color, restore_color)
    last_error = None

    def tick():
        nonlocal last_error
        try:
            colors = load_colors()
            if not colors and controller.owner is None:
                last_error = None
                return
            pid = foreground.pid
            if not use_kwin:
                import re
                window = subprocess.check_output(
                    ["xprop", "-root", "_NET_ACTIVE_WINDOW"], text=True, timeout=2)
                match = re.search(r"0x[0-9a-fA-F]+", window)
                pid = 0
                if match and int(match[0], 16):
                    info = subprocess.check_output(
                        ["xprop", "-id", match[0], "_NET_WM_PID"], text=True, timeout=2)
                    value = re.search(r"=\s*(\d+)", info)
                    pid = int(value[1]) if value else 0
            controller.update(colors, process_games(), pid)
            if controller.color is not None:
                current = tuple(map(int, (LED_DIR / "multi_intensity").read_text().split()))
                if current != controller.color:
                    apply_color(controller.color)
            last_error = None
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            if str(error) != last_error:
                print(f"Spielfarben: {error}", file=sys.stderr, flush=True)
                last_error = str(error)

    def cleanup():
        try:
            controller.close()
        except (OSError, subprocess.SubprocessError) as error:
            print(f"Standardfarbe konnte nicht wiederhergestellt werden: {error}",
                  file=sys.stderr, flush=True)
        try:
            if use_kwin:
                kwin("unloadScript", [plugin])
                script.unlink(missing_ok=True)
        except (OSError, RuntimeError) as error:
            print(f"KWin-Aufräumen fehlgeschlagen: {error}", file=sys.stderr, flush=True)

    app.aboutToQuit.connect(cleanup)
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(1000)
    tick()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
