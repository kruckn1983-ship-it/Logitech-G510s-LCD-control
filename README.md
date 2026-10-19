# Logitech G510s – Software

![Lizenz: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3-blue.svg)
![Plattform: Arch Linux](https://img.shields.io/badge/platform-Arch%20Linux-1793d1.svg)
![G510s: in Entwicklung](https://img.shields.io/badge/G510s-in%20Entwicklung-orange.svg)

**Ein von Grund auf entwickelter Linux-Treiber mit grafischer Oberfläche für die Logitech G510s** – mit funktionierendem LCD, Hintergrundbeleuchtung und G-Tasten-Makros. Logitechs eigene Software gibt es nur für Windows; andere Lösungen sind veraltet, verlassen oder unvollständig. Dieses Projekt kommuniziert deshalb direkt mit dem USB-/HID-Protokoll der Tastatur.

## Herunterladen und installieren

```sh
git clone https://github.com/grumpybollocks/Logitech-G510s-LCD-control.git
cd Logitech-G510s-LCD-control
./install.sh
```

`install.sh` kümmert sich um alle Abhängigkeiten. Das Skript meldet jeweils, was bereits installiert ist und was noch hinzukommt – `pacman` wird nie still im Hintergrund ausgeführt. Außerdem baut es den LCD-Treiber, konvertiert die Beschriftungsschriftart, richtet die systemd-Dienste ein und erstellt Desktop-Verknüpfungen. Das Skript kann gefahrlos erneut ausgeführt werden. Einmalig werden das `sudo`-Passwort (für udev-Regeln und Paketinstallationen) und das Ab- und erneute Anstecken der Tastatur benötigt, damit die Regeln wirksam werden.

Installierte Pakete und ihre Aufgaben:

| Paket | Verwendung |
| --- | --- |
| `python-pyqt5`, `python-pillow`, `python-evdev` | Grafische Oberfläche, Bildimport und Auslesen von Tastaturereignissen |
| `ydotool` | Wiedergabe von Makro-Tastenanschlägen; bringt eine eigene `uinput`-udev-Regel und `ydotool.service` mit |
| `freetype2` | Darstellung der benutzerdefinierten LCD-Schriftart |
| `zenity` | Bestätigungsdialog beim Neustart über die Desktop-Verknüpfung |
| `playerctl` | Titel, Interpret und Laufzeit des aktuell wiedergegebenen Mediums für die Mediensensoren |
| `wmctrl` | Fenstertitel als Ersatz für generische Audiostream-Namen, etwa bei Spielen ohne MPRIS |
| `libg15`, `libg15render` | LCD-Treiber; Quellcode liegt unter `drivers/` und wird beim Installieren nach `/usr/local` gebaut (kein AUR nötig) |

Unterstützt werden Arch/Manjaro, Fedora/Nobara und Debian/Ubuntu/Mint (Paketnamen siehe `scripts/install-deps.sh`). Ein fertiges Installationsmedium (`.run`, `.tar.gz`, `.iso`) wird bei jeder Änderung automatisch gebaut – siehe [INSTALLATION.md](INSTALLATION.md).

**Installation überprüfen:**

```sh
systemctl --user status g510-lcd-stats.service g510-lcd-buttons.service g510-macro-daemon.service
```

Alle drei Dienste sollten `active (running)` anzeigen. Falls das LCD nicht sofort aufleuchtet, trenne die Tastatur kurz vom Rechner und schließe sie wieder an.

**Enthaltene Funktionen:**

- Dunkle Oberfläche mit linker Navigation, Übersicht und Live-LCD-Vorschau; Einstellungen rechts neben dem LCD-Editor, Speichern und Status unten. Fenster frei vergrößerbar und maximierbar; **F11** oder **Vollbild** nutzt den ganzen Bildschirm, **Esc** verlässt Vollbild. Die LCD-Vorschau skaliert proportional, kleinere Fenster bieten bei Bedarf Scrollleisten.
- Live-Anzeige von CPU, RAM, VRAM und Temperatur auf dem eingebauten LCD
- Kompakte Systemvorlage mit 20 separat gemessenen CPU-Thread-Balken (i9-10850K: 10 Kerne/20 Threads), CPU-/GPU-Temperatur, GPU-/VRAM-Balken, RAM-Füllbalken, Uhrzeit und Netzwerk-Up-/Download. Eingerahmte Bereiche bleiben im Editor bearbeitbar.
- Vollständige RGB-Steuerung der Tastaturbeleuchtung
- G-Tasten-Makros mit den Profilen M1, M2 und M3
- Editor für eigene Bildschirme: Auswahl per Dropdown; System, Media Center, Spiele und Netzwerk gestalten, zusätzliche Screens ohne feste Anzahl anlegen, umbenennen und löschen. Die eingebaute Uhr bleibt unveränderbar. L1 blättert durch die fünf vorhandenen und anschließend alle eigenen Bildschirme.
- Uhr-Screen mit **20 fertigen Designs**: Digital pur (bisheriges Layout), Analog-/Digital-Kombinationen, Siebensegment, Binäruhr, Punktmatrix, Kalender und weitere Varianten. Im Uhr-Screen blättern **L2 zurück / L3 weiter** im Kreis; alternativ im Tool unter **Uhr-Design** auswählen. Die letzte Auswahl bleibt über Neustarts erhalten. Lokale Systemzeit, deutsche Datumsanzeige, keine zusätzlichen Schriftdateien.
- Bildschirmabhängige Funktionstasten L2–L5: über die Navigation **LCD-Tasten** einstellbar. Media Center startet mit vorheriger Titel, nächster Titel, Play und Pause; Uhr mit vorherigem/nächstem Uhr-Layout; andere Screens zunächst unbelegt. Bereits gespeicherte Belegungen bleiben unverändert.
- Netzwerkvorlage mit aktiver Schnittstelle, Download-/Uploadrate (KiB/s bzw. MiB/s), zwei getrennten Verlaufsgrafiken der letzten 60 Messwerte und lokaler IPv4-Adresse. Die Diagramme liegen mit Abstand rechts neben den Zahlen und sind im Editor verschiebbar und skalierbar. Kein Speedtest oder Internet-Verfügbarkeitstest. Kein separater Lüftersteuerungsbereich; BIOS-Regelung und LACT bleiben unabhängig.
- Kleiner Winamp auf der Tastatur: animierte Equalizer-Balken sowie Titel, Interpret und Laufzeit des aktuell wiedergegebenen Mediums
- Fortschrittsbalken für Medien mit einer bekannten Laufzeit
- Während der Wiedergabe wechselt das LCD automatisch zum Media Center bzw. zur Spieleansicht. Manuelle Auswahl per L1 oder Tool hat Vorrang bis mindestens fünf Sekunden ohne Wiedergabe; ohne manuelle Auswahl kehrt die Anzeige zur Systemübersicht zurück.
- Läuft ohne Root-Rechte unter dem normalen Benutzerkonto, startet bei der Anmeldung und übersteht Neustarts

![G510s-Steuerungsanwendung – v1](docs/screenshots/g510s-control-v1.png)

## Audio-Visualisierung

Platziere einen Visualizer auf einem bearbeitbaren Bildschirm. Das LCD zeigt dann einen kleinen Live-Equalizer mit zum Musiksignal ausschlagenden Balken sowie Titel, Interpret und Laufzeit.

Der Visualizer greift nicht gezielt auf Spotify, den Browser oder eine bestimmte Anwendung zu. Stattdessen erfasst er den Ton, der gerade über die Lautsprecher ausgegeben wird. Dadurch funktioniert er gleichermaßen mit Spotify, YouTube im Browser, VLC, Spielen und anderen Anwendungen – ohne zusätzliche Konfiguration und ohne Synchronisationsprobleme mit der gerade aktiven Anwendung. Die Größe lässt sich wie bei jedem anderen Element ändern; zusätzlicher Platz zeigt mehr Balken statt nur größere Balken.

## Funktionsweise

Die PyQt5-Anwendung `g510_app.py` kommuniziert direkt mit `/dev/g510-lcd` und `/dev/g510-keys`. Sie verwendet stabile symbolische Verknüpfungen statt unzuverlässiger Gerätenummern und ist nicht auf `g15daemon` angewiesen, dessen Tastenzuordnungen für dieses Modell falsch sind. Die Anwendung läuft unauffällig als drei systemd-Dienste des Benutzers.

## Entwicklung und Modulstruktur

Die Oberfläche und ihre LCD-Daten sind nach Aufgaben getrennt:

| Modul | Aufgabe |
| --- | --- |
| [`src/g510_app.py`](src/g510_app.py) | Fenster, Seiten und Verbindung zu den Diensten |
| [`src/g510_layouts.py`](src/g510_layouts.py) | Sensorbeschreibungen, LCD-Grenzen und Layoutvorlagen; ohne Qt und Dateizugriffe |
| [`src/g510_layout_store.py`](src/g510_layout_store.py) | Lesen und Schreiben von Layouts und Spielepositionen mit explizit übergebenen Dateipfaden |
| [`src/g510_screen_canvas.py`](src/g510_screen_canvas.py) | Skalierte LCD-Vorschau, Auswahl, Verschieben und Größenänderungen |
| [`src/g510_preview.py`](src/g510_preview.py) | Aufruf des nativen Renderers und Lesen seiner Bild-/Positionsausgabe |
| [`src/g510_theme.py`](src/g510_theme.py) | Gemeinsames dunkles Oberflächendesign |
| [`src/g510_screen_keys.py`](src/g510_screen_keys.py) | Screenkatalog, Tastenaktionen und gespeicherte Uhr-Auswahl |
| [`src/g510_lcd_stats.c`](src/g510_lcd_stats.c) | Sensorerfassung und LCD-Dienst |
| [`src/clock_layouts.h`](src/clock_layouts.h) | Internes C-Uhrmodul mit den 20 Designs; vom Renderer eingebunden |

Installer, Rebuild-Skript, Paketbau und CI verwenden denselben
[`scripts/build.sh`](scripts/build.sh)-Einstiegspunkt:

```sh
# Nur bauen, ohne sudo, Treiberinstallation oder Dienstneustart:
bash scripts/build.sh

# Bei Bedarf auch die vorhandenen Schriftquellen neu konvertieren:
bash scripts/build.sh --fonts

# Getrenntes Ausgabeverzeichnis und eingebetteter Installationspfad:
bash scripts/build.sh --output-dir /tmp/g510-build --project-dir /usr/lib/g510-lcd

# Regressionstests ohne angeschlossene Tastatur:
PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -q
```

Der Build benötigt GCC, `pkg-config`, FreeType und die installierten
G15-Bibliotheken; die Tests zusätzlich PyQt5, Pillow und evdev.
Beide Programme werden erst nach erfolgreichen Compilerläufen ersetzt.
Compiler- und Abhängigkeitsfehler brechen den Build ab und lassen die bisherigen
Programme unverändert. Das bestehende
[`scripts/rebuild.sh`](scripts/rebuild.sh) baut zusätzlich die Schriften und
startet danach die beiden LCD-Dienste neu. Ohne interaktive Eingabe wartet es
nicht auf Enter; `G510_NONINTERACTIVE=1` unterdrückt die Pause auch im Terminal.

Das Refactoring verändert weder Screen-IDs noch Layoutdateiformat,
Tastenbelegungen oder das Verzeichnis der persönlichen Einstellungen.
Die CI führt vor dem Erstellen des Installationsmediums auch die Regressionstests aus.

## Projektstatus

- **Öffentlich** auf GitHub.
- **`main`**: mit `v1.0` markiert (LCD-Statistiken, Beleuchtung und G-Tasten-Makros) – stabil und bestätigt. Die analoge Uhr, Verbesserungen an den eigenen Bildschirmen und mehrere echte Fehlerkorrekturen sind inzwischen hinzugekommen und wurden an der realen Tastatur überprüft.
- **`g510s-dev`**: aktive Entwicklung. Änderungen werden erst nach einer Bestätigung an der realen Tastatur in `main` übernommen – das ist eine feste Regel, keine Verzögerung.
- Nicht im AUR; eine Veröffentlichung dort wird derzeit nicht verfolgt.

## Suchst du ein anderes Projekt?

Dieses Repository enthielt früher auch eine separate Anwendung für die Logitech **G910** – eine andere Tastatur mit einer anderen Codebasis. Sie wurde vollständig nach [grumpybollocks/g910-control](https://github.com/grumpybollocks/g910-control) verschoben und ist dort bereits weiterentwickelt. Alle G910-Branches und -Tags wurden ebenfalls aus diesem Repository entfernt (siehe [`BRANCHES.md`](BRANCHES.md) zur vollständigen Geschichte). Seit dem 17.09.2026 befinden sich keine G910-Dateien, -Branches oder -Tags mehr in `main`.

## Dokumentation

- [`G510_README.md`](G510_README.md) – technischer Überblick: Protokoll, behobene Fehler, Schriftkonvertierung und udev-Regeln.
- [`G510_CUSTOM_SCREENS_HOWTO.md`](G510_CUSTOM_SCREENS_HOWTO.md) – Anleitung zum Editor für eigene Bildschirme.

---

## Kleine Geschichten am Rande

Ein paar Dinge aus der Entwicklung, die das Projekt persönlicher machen:

- Auf Wunsch kann die Anwendung freien Speicherplatz auf einem zweiten Laufwerk als Sensor anzeigen. Die Funktion ist optional und zeigt auf Systemen ohne ein solches Laufwerk korrekt „N/A“ an.
- Das Projekt begann neben einer Schwesteranwendung für die Logitech G910 (siehe „Suchst du ein anderes Projekt?“). Diese gemeinsame Vorgeschichte ist noch im Commit-Verlauf dieses Repositorys sichtbar, obwohl die G910-Dateien inzwischen verschoben wurden.
- „wtf are the blue squares for?“ („Wofür sind die blauen Quadrate?“) war echtes, wörtliches Feedback, das eine konkrete Änderung an der Oberfläche ausgelöst hat: Ziehpunkte zum Ändern der Größe erscheinen jetzt erst, wenn sich der Mauszeiger in ihrer Nähe befindet. Ein gutes Beispiel dafür, warum echte Nutzung besser ist als bloßes Raten.

---

## Lizenz

[MIT](LICENSE).
