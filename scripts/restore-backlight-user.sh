#!/bin/bash
set -e

SCRIPT="${HOME:?}/.local/share/g510-lcd/set-backlight-color.sh"
BRIGHTNESS=/sys/class/leds/g15::kbd_backlight/brightness
COLOR=/sys/class/leds/g15::kbd_backlight/multi_intensity

if [ ! -f "$SCRIPT" ]; then
    echo "g510-backlight-restore: no saved backlight color yet" >&2
    exit 0
fi

if [ ! -e "$BRIGHTNESS" ] || [ ! -e "$COLOR" ]; then
    echo "g510-backlight-restore: keyboard LED is not available yet; udev will restore it when detected" >&2
    exit 0
fi

exec /bin/bash "$SCRIPT"
