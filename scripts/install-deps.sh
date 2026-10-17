#!/bin/bash
# Installiert alle Systempakete (Laufzeit + Build-Werkzeuge) für Arch/Manjaro,
# Fedora/Nobara und Debian/Ubuntu/Mint. Erkennt die Distribution automatisch.
set -e

. /etc/os-release 2>/dev/null || true
IDS=" ${ID:-} ${ID_LIKE:-} "

if command -v pacman &>/dev/null; then
    echo "  Erkannt: Arch-Familie (pacman)"
    sudo pacman -S --needed --noconfirm \
        python-pyqt5 python-pillow python-evdev ydotool zenity playerctl wmctrl \
        freetype2 libusb libusb-compat base-devel pkgconf autoconf automake libtool patch bzip2
elif command -v dnf &>/dev/null; then
    echo "  Erkannt: Fedora-Familie (dnf)"
    sudo dnf install -y \
        python3-qt5 python3-pillow python3-evdev ydotool zenity playerctl wmctrl \
        freetype-devel libusb-compat-0.1-devel gcc make pkgconf-pkg-config \
        autoconf automake libtool patch bzip2 systemd-udev
elif command -v apt-get &>/dev/null; then
    echo "  Erkannt: Debian-Familie (apt)"
    sudo apt-get update
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
        python3-pyqt5 python3-pil python3-evdev ydotool zenity playerctl wmctrl \
        libfreetype-dev libusb-dev build-essential pkg-config \
        autoconf automake libtool patch bzip2
else
    echo "  FEHLER: Keine unterstützte Paketverwaltung gefunden (pacman, dnf, apt)."
    echo "  Bitte folgende Programme manuell installieren: Python 3 mit PyQt5, Pillow,"
    echo "  evdev; ydotool, zenity, playerctl, wmctrl; gcc, make, autotools, FreeType- und"
    echo "  libusb-0.1-Entwicklungsdateien. Danach ./install.sh erneut starten."
    exit 1
fi
