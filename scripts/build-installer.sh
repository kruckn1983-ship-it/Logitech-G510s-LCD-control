#!/bin/bash
# Baut das komplette Installationspaket nach dist/:
#   g510s-steuerung-<version>.tar.gz   Archiv des Projekts
#   g510s-steuerung-<version>.run      selbstentpackender Installer (ein Doppelklick/Befehl genügt)
#   g510s-steuerung-<version>.iso      USB-/DVD-Abbild mit .run, tar.gz und Anleitung (benötigt xorriso)
# Läuft lokal und in GitHub Actions (.github/workflows/installationsmedium.yml).
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="${G510_VERSION:-$(git describe --tags --always --dirty 2>/dev/null || date +%Y%m%d)}"
NAME="g510s-steuerung-$VERSION"
OUT="$ROOT/dist"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
rm -rf "$OUT"; mkdir -p "$OUT"

echo "Version: $VERSION"
mkdir -p "$STAGE/g510s-steuerung"
git ls-files -co --exclude-standard -z | grep -zv -e '^\.git/' -e '^dist/' | \
    tar --null -T - -cf - | tar -xf - -C "$STAGE/g510s-steuerung"
echo "$VERSION" > "$STAGE/g510s-steuerung/VERSION"

tar -C "$STAGE" -czf "$OUT/$NAME.tar.gz" g510s-steuerung

# Selbstentpackender Installer: Shell-Kopf + angehängtes tar.gz
RUN="$OUT/$NAME.run"
cat > "$RUN" <<'HEADER'
#!/bin/bash
# G510s-Steuerung - selbstentpackender Installer (Arch/Manjaro, Fedora/Nobara, Debian/Ubuntu/Mint)
# Aufruf:  bash g510s-steuerung-*.run      (nicht mit sudo; Passwort wird bei Bedarf abgefragt)
set -e
if [ "$(id -u)" = "0" ]; then
    echo "Bitte ohne sudo starten - das Skript fragt selbst nach dem Passwort."
    exit 1
fi
TARGET="${G510_INSTALL_DIR:-$HOME/.local/share/g510s-steuerung}"
echo "Entpacke nach $TARGET ..."
mkdir -p "$TARGET"
SKIP=$(awk '/^__ARCHIVE__$/ {print NR + 1; exit 0}' "$0")
tail -n +"$SKIP" "$0" | tar -xz -C "$TARGET" --strip-components=1
cd "$TARGET"
chmod +x install.sh scripts/*.sh 2>/dev/null || true
exec ./install.sh
__ARCHIVE__
HEADER
cat "$OUT/$NAME.tar.gz" >> "$RUN"
chmod +x "$RUN"

# Medium-Abbild (USB-Stick oder DVD)
if command -v xorriso &>/dev/null; then
    ISO_DIR="$STAGE/iso"
    mkdir -p "$ISO_DIR"
    cp "$OUT/$NAME.run" "$OUT/$NAME.tar.gz" "$ISO_DIR/"
    cat > "$ISO_DIR/INSTALLATION.txt" <<EOF
G510s-Steuerung $VERSION - Installation ohne Hilfe

1. Stick/DVD einlegen und den Ordner im Dateimanager öffnen.
2. Terminal in diesem Ordner öffnen und eingeben:   bash $NAME.run
3. Passwort eingeben, wenn danach gefragt wird. Der Rest läuft automatisch
   (Pakete, G510s-Treiber, Dienste, Starter auf dem Desktop).
4. Wird eine Abmeldung verlangt: abmelden, wieder anmelden, Schritt 2 wiederholen.
5. Wenn gefragt: Tastatur aus- und wieder einstecken, Enter drücken.

Unterstützt: Arch/Manjaro, Fedora/Nobara, Debian/Ubuntu/Mint. Internet wird für die
Systempakete benötigt; der Treiber-Quellcode ist enthalten.
EOF
    xorriso -as mkisofs -V "G510S_INSTALL" -J -R -o "$OUT/$NAME.iso" "$ISO_DIR" 2>/dev/null
else
    echo "Hinweis: xorriso fehlt - ISO wird übersprungen."
fi

( cd "$OUT" && sha256sum * > SHA256SUMS )
ls -lh "$OUT"
