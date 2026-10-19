#!/bin/bash
# Rebuilds both G510 LCD programs and restarts their services.
# Run this after editing g510_lcd_stats.c or g510_lcd_buttons.c.
set -e
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
bash "$PROJECT_DIR/scripts/build.sh" --fonts

echo "Restarting services..."
systemctl --user restart g510-lcd-stats.service
systemctl --user restart g510-lcd-buttons.service

echo ""
echo "Done. Status:"
systemctl --user status g510-lcd-stats.service --no-pager -l | head -5
systemctl --user status g510-lcd-buttons.service --no-pager -l | head -5

if [ -t 0 ] && [ -z "${G510_NONINTERACTIVE:-}" ]; then
    read -r -p "Press Enter to close..."
fi
