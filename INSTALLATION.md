# Installation ohne fremde Hilfe

Unterstützt: **Arch/Manjaro**, **Fedora/Nobara**, **Debian/Ubuntu/Mint**. Internet wird für die Systempakete benötigt; der Treiber-Quellcode (libg15 mit G510s-Patch, libg15render, g15fontconvert) liegt bei und wird automatisch gebaut.

## Fertiges Installationsmedium

Bei jeder Änderung auf GitHub baut ein Workflow automatisch (siehe Releases → „Neueste Version“):

- `g510s-steuerung-<Version>.run` – selbstentpackender Installer
- `g510s-steuerung-<Version>.tar.gz` – Archiv des Projekts
- `g510s-steuerung-<Version>.iso` – Abbild für USB-Stick/DVD (enthält `.run`, `.tar.gz`, Anleitung). Es ist ein Datenmedium, kein startbares Live-System.

Installieren:

```bash
bash g510s-steuerung-*.run
```

Nicht mit `sudo` starten; das Passwort wird bei Bedarf abgefragt. Das Skript

1. installiert die Systempakete (`scripts/install-deps.sh`),
2. baut und installiert den G510s-Treiber nach `/usr/local` (`scripts/install-driver.sh`),
3. richtet Gruppe `g510`, udev-Regeln und Dienste ein und legt Starter auf dem Desktop an.

Wenn eine Abmeldung verlangt wird (Gruppenmitgliedschaft): abmelden, anmelden, den Befehl erneut ausführen. Danach die Tastatur aus- und wieder einstecken. Das Programm liegt in `~/.local/share/g510s-steuerung`.

## Medium selbst bauen

```bash
scripts/build-installer.sh      # Ergebnis in dist/ (ISO nur mit installiertem xorriso)
```

## Aus dem Quellordner installieren

```bash
./install.sh
```
