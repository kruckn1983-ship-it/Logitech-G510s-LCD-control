#!/bin/bash
# Baut und installiert die G510s-Treiberbibliotheken aus dem mitgelieferten
# Quellcode nach /usr/local (unabhängig von AUR/Paketquellen):
#   - libg15 1.2.7 + G510-Patch (drivers/libg15-g510.patch)
#   - libg15render (mit FreeType-Unterstützung) inkl. g15fontconvert
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
PREFIX=/usr/local
BUILD="$(mktemp -d)"
trap 'rm -rf "$BUILD"' EXIT
JOBS="$(nproc 2>/dev/null || echo 2)"

if [ -z "$G510_FORCE_DRIVER" ] && [ -e "$PREFIX/lib/libg15.so" ] && [ -e "$PREFIX/lib/libg15render.so" ] \
   && [ -x "$PREFIX/bin/g15fontconvert" ] && grep -q g15r_loadG15Font "$PREFIX/include/libg15render.h" 2>/dev/null; then
    echo "  [ok] Treiber bereits in $PREFIX installiert (G510_FORCE_DRIVER=1 erzwingt Neubau)."
    exit 0
fi

echo "  Baue libg15 (mit G510/G510s-Patch)..."
tar xjf "$DIR/drivers/libg15-1.2.7.tar.bz2" -C "$BUILD"
(
    cd "$BUILD/libg15-1.2.7"
    patch -p1 -l --binary --no-backup-if-mismatch < "$DIR/drivers/libg15-g510.patch" >/dev/null || \
        patch -p1 -l --no-backup-if-mismatch < "$DIR/drivers/libg15-g510.patch" >/dev/null
    ./configure --prefix="$PREFIX" >/dev/null
    make -j"$JOBS" >/dev/null
    sudo make install >/dev/null
)

echo "  Baue libg15render (mit FreeType) und g15fontconvert..."
cp -r "$DIR/drivers/libg15render" "$BUILD/libg15render"
(
    cd "$BUILD/libg15render"
    autoreconf -fi >/dev/null 2>&1
    CFLAGS="-O2 -I$PREFIX/include $(pkg-config --cflags freetype2)" LDFLAGS="-L$PREFIX/lib" ./configure --prefix="$PREFIX" --enable-ttf >/dev/null
    make -j"$JOBS" >/dev/null
    sudo make install >/dev/null
)

# Fedora/Debian durchsuchen /usr/local/lib standardmäßig nicht immer
echo "$PREFIX/lib" | sudo tee /etc/ld.so.conf.d/g510-local.conf >/dev/null
sudo ldconfig
echo "  Treiber installiert."
