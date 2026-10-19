/* Internal clock renderer; included after the shared text and data-path helpers. */
#ifndef G510_CLOCK_LAYOUTS_H
#define G510_CLOCK_LAYOUTS_H

/* Integer scaling keeps the built-in bitmap digits crisp on the 1-bit LCD. */
static void draw_clock_text(g15canvas *c, const char *text, int font, int scale,
                            int x, int y, int source_y, int height) {
    g15canvas glyphs G15_CANVAS_AUTO = {0};
    g15r_initCanvas(&glyphs);
    g15r_renderString(&glyphs, (unsigned char *)text, 0, font, 0, 0);
    int width = measure_builtin_text_width(text, font);
    for (int row = 0; row < height; row++)
        for (int col = 0; col < width; col++)
            if (g15r_getPixel(&glyphs, col, row + source_y))
                g15r_pixelBox(c, x + col * scale, y + row * scale,
                              x + (col + 1) * scale - 1, y + (row + 1) * scale - 1,
                              G15_COLOR_BLACK, 1, G15_PIXEL_FILL);
}

enum { CLOCK_LAYOUT_COUNT = 20 };

static int read_clock_layout(void) {
    char path[512], value[32];
    snprintf(path, sizeof(path), "%s/clock_layout", data_dir());
    FILE *file = fopen(path, "r");
    if (!file) {
        if (errno == ENOENT) return 0;
        fprintf(stderr, "g510-lcd-stats: cannot read clock layout: %s\n", strerror(errno));
        return -1;
    }
    size_t length = fread(value, 1, sizeof(value) - 1, file);
    int failed = ferror(file);
    fclose(file);
    value[length] = 0;
    char *start = value, *end;
    while (*start && isspace((unsigned char)*start)) start++;
    errno = 0;
    long index = strtol(start, &end, 10);
    while (*end && isspace((unsigned char)*end)) end++;
    if (failed || !length || memchr(value, '\0', length) ||
        !isdigit((unsigned char)*start) || errno ||
        *end || index < 0 || index >= CLOCK_LAYOUT_COUNT || length == sizeof(value) - 1) {
        fprintf(stderr, "g510-lcd-stats: invalid clock layout (expected 0..19): %s\n", path);
        return -1;
    }
    return (int)index;
}

static void clock_center_text(g15canvas *c, const char *text, int y, int x, int width) {
    int text_width = measure_builtin_text_width(text, G15_TEXT_SMALL);
    g15r_renderString(c, (unsigned char *)text, 0, G15_TEXT_SMALL,
                      x + (width - text_width) / 2, y);
}

static void clock_large(g15canvas *c, const char *text, int scale, int x, int y) {
    draw_clock_text(c, text, G15_TEXT_HUGE, scale, x, y, 1, 10);
}

static void clock_frame(g15canvas *c, int x, int y, int width, int height) {
    g15r_pixelBox(c, x, y, x + width - 1, y + height - 1,
                  G15_COLOR_BLACK, 1, G15_PIXEL_NOFILL);
}

static void clock_analog(g15canvas *c, const struct tm *t, int cx, int cy, int radius,
                          int numerals, int seconds) {
    g15r_drawCircle(c, cx, cy, radius, 0, G15_COLOR_BLACK);
    for (int i = 0; i < 12; i++) {
        if (numerals && (i == 0 || i == 6)) continue;
        double angle = i * M_PI / 6;
        int outer = radius - 2, inner = radius - (i % 3 ? 3 : 5);
        g15r_drawLine(c, cx + (int)lround(sin(angle) * inner),
                      cy - (int)lround(cos(angle) * inner),
                      cx + (int)lround(sin(angle) * outer),
                      cy - (int)lround(cos(angle) * outer), G15_COLOR_BLACK);
    }
    if (numerals) {
        clock_center_text(c, "12", cy - radius + 5, cx - 5, 10);
        clock_center_text(c, "6", cy + radius - 9, cx - 3, 6);
    }
    const double angles[] = {
        ((t->tm_hour % 12) + t->tm_min / 60.0) * M_PI / 6,
        (t->tm_min + t->tm_sec / 60.0) * M_PI / 30,
        t->tm_sec * M_PI / 30,
    };
    const int lengths[] = {
        numerals ? radius / 3 : radius / 2, numerals ? radius - 10 : radius - 6, radius - 3
    };
    for (int i = 0; i < (seconds ? 3 : 2); i++)
        g15r_drawLine(c, cx, cy, cx + (int)lround(sin(angles[i]) * lengths[i]),
                      cy - (int)lround(cos(angles[i]) * lengths[i]), G15_COLOR_BLACK);
    g15r_pixelBox(c, cx - 1, cy - 1, cx + 1, cy + 1, G15_COLOR_BLACK, 1, G15_PIXEL_FILL);
}

static void clock_segments(g15canvas *c, const char *digits, int x, int y) {
    static const unsigned char masks[] = {
        0x3f, 0x06, 0x5b, 0x4f, 0x66, 0x6d, 0x7d, 0x07, 0x7f, 0x6f
    };
    const int lines[][4] = {
        {2, 0, 11, 1}, {12, 2, 13, 11}, {12, 14, 13, 23}, {2, 24, 11, 25},
        {0, 14, 1, 23}, {0, 2, 1, 11}, {2, 12, 11, 13},
    };
    for (int i = 0; digits[i]; i++) {
        if (digits[i] == ':') {
            g15r_pixelBox(c, x + 1, y + 7, x + 3, y + 9, G15_COLOR_BLACK, 1, G15_PIXEL_FILL);
            g15r_pixelBox(c, x + 1, y + 17, x + 3, y + 19, G15_COLOR_BLACK, 1, G15_PIXEL_FILL);
            x += 8;
            continue;
        }
        int mask = masks[digits[i] - '0'];
        for (int j = 0; j < 7; j++)
            if (mask & (1 << j))
                g15r_pixelBox(c, x + lines[j][0], y + lines[j][1],
                              x + lines[j][2], y + lines[j][3],
                              G15_COLOR_BLACK, 1, G15_PIXEL_FILL);
        x += 18;
    }
}

static void draw_clock_layout(g15canvas *c, const struct tm *t, int layout) {
    static const char *weekdays[] = {
        "Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"
    };
    char hours[8], seconds[4], date[40], numeric_date[16], full_time[12], hh[4], mm[4];
    strftime(hours, sizeof(hours), "%H:%M", t);
    strftime(seconds, sizeof(seconds), "%S", t);
    strftime(numeric_date, sizeof(numeric_date), "%d.%m.%Y", t);
    snprintf(date, sizeof(date), "%s, %s", weekdays[t->tm_wday], numeric_date);
    strftime(full_time, sizeof(full_time), "%H:%M:%S", t);
    strftime(hh, sizeof(hh), "%H", t);
    strftime(mm, sizeof(mm), "%M", t);

    if (layout == 1) {
        clock_large(c, full_time, 2, 28, 5);
        g15r_drawLine(c, 28, 29, 131, 29, G15_COLOR_BLACK);
        clock_center_text(c, date, 36, 0, 160);
    } else if (layout == 2) {
        clock_frame(c, 3, 2, 104, 31);
        clock_frame(c, 111, 2, 46, 31);
        clock_large(c, hours, 2, 24, 7);
        clock_center_text(c, "SEKUNDEN", 6, 112, 44);
        clock_large(c, seconds, 1, 128, 18);
        clock_center_text(c, date, 36, 0, 160);
    } else if (layout == 3) {
        const char *values[] = {hh, mm, seconds};
        const char *labels[] = {"STUNDEN", "MINUTEN", "SEKUNDEN"};
        for (int i = 0; i < 3; i++) {
            int x = 5 + 51 * i;
            clock_frame(c, x, 1, 47, 32);
            clock_center_text(c, labels[i], 4, x, 47);
            clock_large(c, values[i], 2, x + 10, 12);
        }
        clock_center_text(c, date, 36, 0, 160);
    } else if (layout == 4) {
        clock_segments(c, hours, 25, 3);
        draw_clock_text(c, seconds, G15_TEXT_LARGE, 2, 113, 15, 0, 7);
        clock_center_text(c, date, 36, 0, 160);
    } else if (layout == 5) {
        g15canvas solid G15_CANVAS_AUTO = {0};
        g15r_initCanvas(&solid);
        clock_large(&solid, hours, 3, 13, 1);
        for (int y = 1; y < 31; y++)
            for (int x = 13; x < 106; x++)
                if (g15r_getPixel(&solid, x, y) &&
                    (!g15r_getPixel(&solid, x - 1, y) || !g15r_getPixel(&solid, x + 1, y) ||
                     !g15r_getPixel(&solid, x, y - 1) || !g15r_getPixel(&solid, x, y + 1)))
                    g15r_setPixel(c, x, y, G15_COLOR_BLACK);
        clock_large(c, seconds, 2, 119, 11);
        clock_center_text(c, date, 36, 0, 160);
    } else if (layout == 6) {
        g15canvas text G15_CANVAS_AUTO = {0};
        g15r_initCanvas(&text);
        clock_large(&text, hours, 3, 14, 2);
        clock_large(&text, seconds, 2, 119, 12);
        for (int y = 1; y < 33; y++)
            for (int x = 4; x < 156; x++)
                g15r_setPixel(c, x, y, g15r_getPixel(&text, x, y) ? G15_COLOR_WHITE : G15_COLOR_BLACK);
        clock_center_text(c, date, 36, 0, 160);
    } else if (layout == 7 || layout == 8) {
        int face_x = layout == 7 ? 24 : 136;
        int text_x = layout == 7 ? 52 : 5;
        clock_analog(c, t, face_x, 21, 19, 0, 1);
        clock_large(c, hours, 2, text_x + 13, 3);
        clock_center_text(c, seconds, 27, text_x, 102);
        clock_center_text(c, numeric_date, 36, text_x, 102);
    } else if (layout == 9) {
        clock_analog(c, t, 80, 18, 16, 1, 0);
        clock_center_text(c, hours, 5, 3, 49);
        clock_center_text(c, seconds, 24, 109, 48);
        clock_center_text(c, date, 36, 0, 160);
    } else if (layout == 10) {
        char digits[8];
        snprintf(digits, sizeof(digits), "%s%s%s", hh, mm, seconds);
        const char *labels[] = {"STD", "MIN", "SEK"};
        for (int i = 0; i < 3; i++) clock_center_text(c, labels[i], 1, 29 + i * 36, 30);
        for (int i = 0; i < 6; i++)
            for (int bit = 0; bit < 4; bit++) {
                int x = 29 + (i / 2) * 36 + (i % 2) * 15, y = 9 + bit * 6;
                g15r_pixelBox(c, x, y, x + 9, y + 3, G15_COLOR_BLACK, 1,
                              (digits[i] - '0') & (8 >> bit) ? G15_PIXEL_FILL : G15_PIXEL_NOFILL);
            }
        clock_center_text(c, date, 36, 0, 160);
    } else if (layout == 11) {
        const char *values[] = {hh, mm, seconds};
        const char *labels[] = {"STUNDE", "MINUTE", "SEKUNDE"};
        for (int i = 0; i < 3; i++) {
            int x = 8 + i * 50;
            clock_center_text(c, labels[i], 3, x, 44);
            clock_large(c, values[i], 2, x + 9, 13);
            if (i < 2) g15r_drawLine(c, x + 46, 3, x + 46, 31, G15_COLOR_BLACK);
        }
        clock_center_text(c, date, 36, 0, 160);
    } else if (layout == 12) {
        clock_large(c, hh, 2, 19, 1);
        clock_large(c, mm, 2, 19, 22);
        g15r_drawLine(c, 59, 3, 59, 39, G15_COLOR_BLACK);
        clock_center_text(c, weekdays[t->tm_wday], 5, 64, 91);
        clock_center_text(c, numeric_date, 16, 64, 91);
        clock_center_text(c, "SEKUNDEN", 28, 64, 91);
        clock_center_text(c, seconds, 36, 64, 91);
    } else if (layout == 13) {
        clock_large(c, hours, 2, 27, 2);
        clock_large(c, seconds, 1, 116, 12);
        clock_frame(c, 15, 26, 130, 6);
        int fill = (int)lround(t->tm_sec * 126.0 / 59);
        if (fill) g15r_pixelBox(c, 17, 28, 16 + fill, 29, G15_COLOR_BLACK, 1, G15_PIXEL_FILL);
        clock_center_text(c, date, 36, 0, 160);
    } else if (layout == 14) {
        char day[4], month_year[12];
        strftime(day, sizeof(day), "%d", t);
        strftime(month_year, sizeof(month_year), "%m.%Y", t);
        clock_frame(c, 4, 2, 46, 39);
        clock_center_text(c, weekdays[t->tm_wday], 5, 5, 44);
        clock_large(c, day, 2, 14, 14);
        clock_center_text(c, month_year, 35, 5, 44);
        clock_large(c, hours, 2, 68, 5);
        clock_center_text(c, "SEKUNDEN", 29, 56, 100);
        clock_center_text(c, seconds, 36, 56, 100);
    } else if (layout == 15) {
        const char *values[] = {hh, mm};
        for (int i = 0; i < 2; i++) {
            int x = 12 + 56 * i;
            clock_frame(c, x, 1, 49, 31);
            clock_large(c, values[i], 2, x + 12, 6);
            g15r_drawLine(c, x, 16, x + 4, 16, G15_COLOR_BLACK);
            g15r_drawLine(c, x + 44, 16, x + 48, 16, G15_COLOR_BLACK);
        }
        clock_center_text(c, "SEK", 6, 124, 28);
        clock_large(c, seconds, 1, 132, 19);
        clock_center_text(c, date, 36, 0, 160);
    } else if (layout == 16) {
        g15canvas glyphs G15_CANVAS_AUTO = {0};
        g15r_initCanvas(&glyphs);
        g15r_renderString(&glyphs, (unsigned char *)full_time, 0, G15_TEXT_SMALL, 0, 0);
        int width = measure_builtin_text_width(full_time, G15_TEXT_SMALL);
        for (int y = 0; y < 5; y++)
            for (int x = 0; x < width; x++)
                if (g15r_getPixel(&glyphs, x, y))
                    g15r_pixelBox(c, 18 + x * 4, 5 + y * 4, 19 + x * 4, 6 + y * 4,
                                  G15_COLOR_BLACK, 1, G15_PIXEL_FILL);
        clock_center_text(c, date, 36, 0, 160);
    } else if (layout == 17) {
        clock_center_text(c, weekdays[t->tm_wday], 2, 0, 160);
        clock_large(c, hours, 2, 49, 11);
        clock_center_text(c, seconds, 25, 124, 30);
        clock_center_text(c, numeric_date, 36, 0, 160);
    } else if (layout == 18) {
        clock_frame(c, 4, 2, 152, 39);
        g15r_renderString(c, (unsigned char *)"> LOCAL TIME", 0, G15_TEXT_SMALL, 9, 6);
        clock_large(c, full_time, 1, 9, 17);
        g15r_renderString(c, (unsigned char *)"_", 0, G15_TEXT_SMALL, 65, 22);
        g15r_renderString(c, (unsigned char *)date, 0, G15_TEXT_SMALL, 9, 32);
    } else if (layout == 19) {
        clock_large(c, full_time, 2, 28, 1);
        clock_center_text(c, date, 24, 0, 160);
        int elapsed = t->tm_hour * 3600 + t->tm_min * 60 + t->tm_sec;
        g15r_drawLine(c, 18, 38, 141, 38, G15_COLOR_BLACK);
        for (int i = 0; i <= 4; i++)
            g15r_drawLine(c, 18 + i * 123 / 4, 36, 18 + i * 123 / 4, 40, G15_COLOR_BLACK);
        int position = 18 + (int)lround(elapsed * 123.0 / 86399);
        g15r_pixelBox(c, position - 1, 33, position + 1, 35, G15_COLOR_BLACK, 1, G15_PIXEL_FILL);
    } else {

        /* Fixed slots prevent the group moving as narrow digits change. */
        const int main_width = 31 * 3, seconds_width = 15 * 2, gap = 9;
        int x = (G15_LCD_WIDTH - main_width - gap - seconds_width) / 2;
        int seconds_x = x + main_width + gap;
        draw_clock_text(c, hours, G15_TEXT_HUGE, 3, x, 1, 1, 10);
        draw_clock_text(c, seconds, G15_TEXT_LARGE, 2, seconds_x, 17, 0, 7);
        g15r_renderString(c, (unsigned char *)"SEK", 0, G15_TEXT_SMALL,
                          seconds_x + (seconds_width - measure_builtin_text_width("SEK", G15_TEXT_SMALL)) / 2, 6);
        g15r_drawLine(c, x, 33, G15_LCD_WIDTH - x - 1, 33, G15_COLOR_BLACK);
        int date_x = (G15_LCD_WIDTH - measure_builtin_text_width(date, G15_TEXT_SMALL)) / 2;
        g15r_renderString(c, (unsigned char *)date, 0, G15_TEXT_SMALL, date_x, 36);
    }
}

static void draw_clock_screen(g15canvas *c) {
    time_t now = time(NULL);
    struct tm *t = localtime(&now);
    int layout = read_clock_layout();
    if (!t || layout < 0) {
        if (!t) fprintf(stderr, "g510-lcd-stats: cannot convert clock time: %s\n", strerror(errno));
        clock_center_text(c, layout < 0 ? "UHR-LAYOUT UNGUELTIG" : "UHRZEIT NICHT VERFUEGBAR", 18, 0, 160);
        return;
    }
    draw_clock_layout(c, t, layout);
}

#endif
