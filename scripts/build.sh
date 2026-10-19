#!/bin/bash
# Build only: no dependency installation, device access or service changes.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_DIR="$ROOT"
OUTPUT_DIR="$ROOT/src"
CONVERT_FONTS=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --project-dir|--output-dir)
            if [ "$#" -lt 2 ] || [ -z "$2" ]; then
                echo "Missing value for $1" >&2
                exit 2
            fi
            if [ "$1" = "--project-dir" ]; then PROJECT_DIR="$2"; else OUTPUT_DIR="$2"; fi
            shift 2
            ;;
        --fonts) CONVERT_FONTS=1; shift ;;
        *) echo "Unknown build option: $1" >&2; exit 2 ;;
    esac
done

if [ "$CONVERT_FONTS" = 1 ]; then
    for spec in "FONT.otf:lcd-label-8.fnt" "FALLBACK.ttf:lcd-label-8-fallback.fnt"; do
        source="$ROOT/fonts/source-ttf/${spec%%:*}"
        destination="$ROOT/fonts/${spec#*:}"
        if [ ! -f "$source" ]; then
            echo "Font source missing: $source; renderer will use its fallback." >&2
        elif ! command -v g15fontconvert >/dev/null; then
            echo "g15fontconvert missing; keeping existing fonts and renderer fallback." >&2
            break
        else
            g15fontconvert -s 8 -i "$source" -o "$destination"
        fi
    done
fi

mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"
STAGE="$(mktemp -d "$OUTPUT_DIR/.g510-build.XXXXXX")"
trap 'rm -f "$STAGE/g510_lcd_stats" "$STAGE/g510_lcd_buttons"; rmdir "$STAGE"' EXIT
FT_CFLAGS_TEXT="$(pkg-config --cflags freetype2)"
FT_LIBS_TEXT="$(pkg-config --libs freetype2)"
read -r -a FT_CFLAGS <<< "$FT_CFLAGS_TEXT"
read -r -a FT_LIBS <<< "$FT_LIBS_TEXT"

echo "Building LCD renderer..."
# These FreeType flags must match libg15render's canvas struct layout.
gcc -I/usr/local/include -L/usr/local/lib -Wl,-rpath,/usr/local/lib \
    "${FT_CFLAGS[@]}" "-DPROJECT_DIR=\"$PROJECT_DIR\"" \
    "$ROOT/src/g510_lcd_stats.c" -o "$STAGE/g510_lcd_stats" \
    -lg15render "${FT_LIBS[@]}" -lm
echo "Building LCD key listener..."
gcc "$ROOT/src/g510_lcd_buttons.c" -o "$STAGE/g510_lcd_buttons"

# Publish only after both compilers succeeded; running executables remain valid.
mv "$STAGE/g510_lcd_stats" "$OUTPUT_DIR/g510_lcd_stats"
mv "$STAGE/g510_lcd_buttons" "$OUTPUT_DIR/g510_lcd_buttons"
