#!/bin/bash
# Restores the last-applied keyboard backlight color on hotplug (boot
# or replug). Run automatically by 99-g510-lcd.rules whenever the LED
# device appears.
#
# Runs as root via udev, which has no per-user $HOME to resolve
# directly -- finds whichever user actually has the active seat0
# session via loginctl instead, then reads their own saved color from
# ~/.local/share/g510-lcd/set-backlight-color.sh (written by
# g510_app.py every time Apply/Set as Default is clicked). This is
# genuinely single-seat desktop hardware; broader multi-user handling
# is out of scope.
#
# Installed at a FIXED location by both install.sh and the PKGBUILD
# (unlike the old __PROJECT_DIR__-substituted approach) so this exact
# file -- and the udev rule line that calls it -- never needs to know
# whether it's a dev checkout or a real package.
if [ "${1:-}" = "--user" ]; then
    SCRIPT="$HOME/.local/share/g510-lcd/set-backlight-color.sh"
    if [ ! -f "$SCRIPT" ]; then
        echo "G510: no saved backlight color yet."
        exit 0
    fi
    # The user manager can start before udev has granted LED access.
    for ((attempt = 0; attempt < 30; attempt++)); do
        if [ -w "/sys/class/leds/g15::kbd_backlight/brightness" ] &&
           [ -w "/sys/class/leds/g15::kbd_backlight/multi_intensity" ]; then
            exec /bin/bash -e "$SCRIPT"
        fi
        sleep 1
    done
    echo "G510: backlight unavailable or not writable after 30 seconds; check keyboard and udev permissions." >&2
    exit 1
elif [ "$#" -gt 0 ]; then
    echo "Usage: $0 [--user]" >&2
    exit 2
fi

USER_NAME=$(loginctl list-sessions --no-legend 2>/dev/null | awk '$4=="seat0"{print $3; exit}')
[ -z "$USER_NAME" ] && exit 0

USER_HOME=$(getent passwd "$USER_NAME" | cut -d: -f6)
[ -z "$USER_HOME" ] && exit 0

SCRIPT="$USER_HOME/.local/share/g510-lcd/set-backlight-color.sh"
[ -x "$SCRIPT" ] && exec "$SCRIPT"
exit 0
