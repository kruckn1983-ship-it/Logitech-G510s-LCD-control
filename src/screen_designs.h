/* Built-in layouts share the live sensors, media state and network history.
   Index zero is deliberately handled by the existing editable renderer. */
#ifndef G510_SCREEN_DESIGNS_H
#define G510_SCREEN_DESIGNS_H

enum { SCREEN_DESIGN_COUNT = 20 };

static int read_screen_design(int screen) {
    if (screen < 2 || screen > 5) return 0;
    char path[512], value[32];
    snprintf(path, sizeof(path), "%s/screen_design_%d", data_dir(), screen);
    FILE *file = fopen(path, "r");
    if (!file) {
        if (errno == ENOENT) return 0;
        fprintf(stderr, "g510-lcd-stats: cannot read screen design: %s\n", strerror(errno));
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
    if (failed || !length || memchr(value, 0, length) ||
        !isdigit((unsigned char)*start) || errno || *end || index < 0 ||
        index >= SCREEN_DESIGN_COUNT || length == sizeof(value) - 1) {
        fprintf(stderr, "g510-lcd-stats: invalid screen design: %s\n", path);
        return -1;
    }
    return (int)index;
}

typedef struct { int x, y, w, h; } design_rect_t;

static void design_frame(g15canvas *c, int x, int y, int w, int h) {
    g15r_pixelBox(c, x, y, x + w - 1, y + h - 1,
                  G15_COLOR_BLACK, 1, G15_PIXEL_NOFILL);
}

static void design_text(g15canvas *c, const char *value, int font,
                         int x, int y, int width, int height, int center) {
    char text[256];
    snprintf(text, sizeof(text), "%s", value);
    truncate_builtin_text(text, font, width);
    g15canvas glyphs G15_CANVAS_AUTO = {0};
    g15r_initCanvas(&glyphs);
    g15r_renderString(&glyphs, (unsigned char *)text, 0, font, 0, 0);
    int offset = center ? (width - measure_builtin_text_width(text, font)) / 2 : 0;
    for (int row = 0; row < height; row++)
        for (int col = 0; col < width - offset; col++)
            if (g15r_getPixel(&glyphs, col, row))
                g15r_setPixel(c, x + offset + col, y + row, G15_COLOR_BLACK);
}

static double design_value(g15canvas *c, const char *key, const char *prefix,
                            int x, int y, int width, int font) {
    char value[128], text[160];
    double percent;
    get_sensor_value(key, !strncmp(key, "NET_", 4) ? "compact" : "", &percent,
                     value, sizeof(value));
    snprintf(text, sizeof(text), "%s%s", prefix, value);
    while (font > G15_TEXT_SMALL && measure_builtin_text_width(text, font) > width)
        font--;
    design_text(c, text, font, x, y, width, font == G15_TEXT_HUGE ? 11 : 8, 0);
    return percent;
}

static void design_bar(g15canvas *c, double percent, int x, int y, int w, int h) {
    design_frame(c, x, y, w, h);
    int fill = percent < 0 ? 0 : (int)lround(fmin(100, percent) * (w - 2) / 100);
    if (fill > 0)
        g15r_pixelBox(c, x + 1, y + 1, x + fill, y + h - 2,
                      G15_COLOR_BLACK, 1, G15_PIXEL_FILL);
}

static void design_metric(g15canvas *c, const char *key, const char *label,
                           int x, int y, int w, int h, int large, int bar) {
    design_text(c, label, G15_TEXT_SMALL, x, y, w, 6, 0);
    double value = design_value(c, key, "", x, y + 8, w,
                                 large ? G15_TEXT_HUGE : G15_TEXT_MED);
    if (bar) design_bar(c, value, x, y + h - 5, w, 5);
}

static void design_threads(g15canvas *c, int x, int y, int width, int height, int rows) {
    int columns = CPU_CORE_SENSOR_COUNT / rows;
    int cell_w = width / columns, cell_h = height / rows;
    for (int i = 0; i < CPU_CORE_SENSOR_COUNT; i++) {
        char key[24], value[32]; double percent;
        snprintf(key, sizeof(key), "CPU_CORE_%d", i);
        get_sensor_value(key, "", &percent, value, sizeof(value));
        int bx = x + (i % columns) * cell_w, by = y + (i / columns) * cell_h;
        int w = cell_w - 1, h = cell_h - 1;
        design_frame(c, bx, by, w, h);
        int fill = percent < 0 ? 0 : (int)lround(fmin(100, percent) * (h - 2) / 100);
        if (fill > 0) g15r_pixelBox(c, bx + 1, by + h - 1 - fill, bx + w - 2,
                                    by + h - 2, G15_COLOR_BLACK, 1, G15_PIXEL_FILL);
    }
}

static void design_dial(g15canvas *c, const char *key, const char *label,
                         int cx, int cy, int radius) {
    char value[40]; double percent;
    get_sensor_value(key, "", &percent, value, sizeof(value));
    g15r_drawCircle(c, cx, cy, radius, 0, G15_COLOR_BLACK);
    if (percent >= 0) {
        double angle = (-135 + fmin(100, percent) * 2.7) * M_PI / 180;
        g15r_drawLine(c, cx, cy, cx + (int)lround(sin(angle) * (radius - 2)),
                      cy - (int)lround(cos(angle) * (radius - 2)), G15_COLOR_BLACK);
    }
    design_text(c, label, G15_TEXT_SMALL, cx - radius, cy + radius + 2,
                 radius * 2 + 1, 6, 1);
}

static void design_system(g15canvas *c, int index) {
    switch (index) {
    case 1:
        design_dial(c, "CPU_PCT", "CPU", 25, 17, 15);
        design_dial(c, "GPU_PCT", "GPU", 79, 17, 15);
        design_dial(c, "RAM_PCT", "RAM", 133, 17, 15);
        break;
    case 2:
        design_text(c, "20 CPU-THREADS", 0, 1, 1, 100, 6, 0);
        design_value(c, "CPU_TEMP", "", 108, 1, 50, 0);
        design_threads(c, 1, 11, 158, 31, 2);
        break;
    case 3:
        design_metric(c, "CPU_PCT", "PROZESSOR", 2, 1, 70, 39, 1, 1);
        design_threads(c, 80, 1, 80, 30, 2);
        design_value(c, "CPU_GHZ", "GHZ ", 80, 34, 79, 0);
        break;
    case 4:
        design_metric(c, "GPU_PCT", "GRAFIK", 2, 1, 70, 39, 1, 1);
        design_metric(c, "VRAM_PCT", "VRAM", 82, 1, 76, 21, 0, 0);
        design_value(c, "GPU_EDGE_TEMP", "GPU ", 82, 26, 76, 1);
        design_value(c, "GPU_HOTSPOT_TEMP", "HOT ", 82, 36, 76, 0);
        break;
    case 5:
        design_metric(c, "RAM_PCT", "ARBEITSSPEICHER", 2, 1, 94, 39, 1, 1);
        design_value(c, "RAM_AMOUNT", "", 101, 1, 58, 0);
        design_metric(c, "SWAP_PCT", "SWAP", 101, 15, 57, 26, 0, 1);
        break;
    case 6:
        design_frame(c, 0, 0, 78, 43); design_frame(c, 82, 0, 78, 43);
        design_metric(c, "CPU_TEMP", "CPU-TEMPERATUR", 3, 3, 72, 36, 1, 1);
        design_metric(c, "GPU_EDGE_TEMP", "GPU-TEMPERATUR", 85, 3, 72, 36, 1, 1);
        break;
    case 7: {
        const char *keys[] = {"CPU_PCT", "GPU_PCT", "RAM_PCT", "VRAM_PCT"};
        const char *labels[] = {"CPU ", "GPU ", "RAM ", "VRAM "};
        for (int i = 0; i < 4; i++) {
            int x = (i % 2) * 82, y = (i / 2) * 23;
            design_frame(c, x, y, 78, 20);
            design_value(c, keys[i], labels[i], x + 3, y + 5, 72, 1);
        } break;
    }
    case 8:
        design_threads(c, 0, 0, 160, 24, 1);
        design_value(c, "CPU_PCT", "CPU ", 1, 27, 76, 1);
        design_value(c, "GPU_PCT", "GPU ", 83, 27, 76, 1);
        design_value(c, "RAM_PCT", "RAM ", 1, 37, 76, 0);
        design_value(c, "CPU_TEMP", "TEMP ", 83, 37, 76, 0);
        break;
    case 9:
        design_threads(c, 0, 0, 100, 43, 2);
        design_value(c, "CPU_TEMP", "CPU ", 104, 2, 55, 0);
        design_value(c, "GPU_EDGE_TEMP", "GPU ", 104, 15, 55, 0);
        design_value(c, "RAM_PCT", "RAM ", 104, 28, 55, 0);
        break;
    case 10:
        design_frame(c, 0, 0, 160, 43);
        design_text(c, "SYSTEM MONITOR", 0, 3, 2, 154, 6, 1);
        design_metric(c, "CPU_PCT", "CPU", 3, 12, 48, 27, 0, 1);
        design_metric(c, "GPU_PCT", "GPU", 56, 12, 48, 27, 0, 1);
        design_metric(c, "RAM_PCT", "RAM", 109, 12, 48, 27, 0, 1);
        break;
    case 11:
        design_value(c, "UPTIME", "> UPTIME ", 1, 1, 158, 0);
        design_value(c, "CPU_PCT", "> CPU ", 1, 11, 77, 0);
        design_value(c, "GPU_PCT", "GPU ", 84, 11, 75, 0);
        design_value(c, "RAM_AMOUNT", "> RAM ", 1, 21, 158, 0);
        design_value(c, "CPU_TEMP", "> CPU ", 1, 33, 77, 0);
        design_value(c, "GPU_EDGE_TEMP", "GPU ", 84, 33, 75, 0);
        break;
    case 12: {
        const char *keys[] = {"CPU_PCT", "GPU_PCT", "RAM_PCT", "VRAM_PCT"};
        const char *labels[] = {"CPU ", "GPU ", "RAM ", "VRAM "};
        for (int i = 0; i < 4; i++) {
            double p = design_value(c, keys[i], labels[i], 1, i * 11, 58, 0);
            design_bar(c, p, 63, i * 11, 96, 8);
        } break;
    }
    case 13:
        design_metric(c, "CPU_PCT", "CPU", 2, 1, 73, 27, 1, 1);
        design_metric(c, "GPU_PCT", "GPU", 85, 1, 73, 27, 1, 1);
        design_value(c, "CPU_TEMP", "", 2, 34, 73, 0);
        design_value(c, "GPU_EDGE_TEMP", "", 85, 34, 73, 0);
        g15r_drawLine(c, 79, 0, 79, 42, G15_COLOR_BLACK);
        break;
    case 14:
        design_value(c, "TIME", "", 1, 0, 158, 2);
        design_value(c, "CPU_PCT", "CPU ", 1, 13, 76, 0);
        design_value(c, "RAM_PCT", "RAM ", 82, 13, 77, 0);
        design_value(c, "NET_UP", "UP ", 1, 25, 158, 0);
        design_value(c, "NET_DOWN", "DN ", 1, 36, 158, 0);
        break;
    case 15:
        design_dial(c, "CPU_PCT", "CPU", 24, 16, 14);
        design_dial(c, "GPU_PCT", "GPU", 75, 16, 14);
        design_metric(c, "RAM_PCT", "RAM", 107, 3, 51, 35, 1, 1);
        break;
    case 16:
        design_threads(c, 1, 1, 158, 32, 1);
        design_value(c, "CPU_TEMP", "CPU ", 1, 36, 77, 0);
        design_value(c, "CPU_GHZ", "GHZ ", 83, 36, 76, 0);
        break;
    case 17:
        design_metric(c, "RAM_PCT", "RAM", 2, 1, 74, 39, 1, 1);
        design_metric(c, "VRAM_PCT", "VRAM", 84, 1, 74, 39, 1, 1);
        break;
    case 18:
        design_value(c, "CPU_PCT", "", 4, 14, 45, 3);
        design_value(c, "GPU_PCT", "", 57, 14, 45, 3);
        design_value(c, "RAM_PCT", "", 110, 14, 45, 3);
        design_text(c, "CPU", 0, 4, 1, 45, 6, 0);
        design_text(c, "GPU", 0, 57, 1, 45, 6, 0);
        design_text(c, "RAM", 0, 110, 1, 45, 6, 0);
        break;
    case 19:
        design_value(c, "CPU_TEMP", "CPU ", 1, 1, 76, 0);
        design_value(c, "GPU_EDGE_TEMP", "GPU ", 83, 1, 76, 0);
        design_threads(c, 1, 12, 158, 20, 1);
        design_value(c, "RAM_PCT", "RAM ", 1, 36, 76, 0);
        design_value(c, "TIME", "", 83, 36, 76, 0);
        break;
    }
}

static void design_history(g15canvas *c, const char *sensor, int x, int y, int w, int h) {
    element_t element = {0};
    snprintf(element.sensor, sizeof(element.sensor), "%s", sensor);
    element.x = x; element.y = y; element.width = w; element.height = h;
    draw_network_history(c, &element);
}

static void design_network(g15canvas *c, int index) {
    switch (index) {
    case 1:
        design_value(c, "NET_DOWN", "DL ", 1, 1, 77, 0);
        design_value(c, "NET_UP", "UL ", 83, 1, 76, 0);
        design_history(c, "NET_DOWN", 1, 12, 76, 29);
        design_history(c, "NET_UP", 83, 12, 76, 29);
        break;
    case 2:
    case 3: {
        const char *key = index == 2 ? "NET_DOWN" : "NET_UP";
        design_value(c, key, index == 2 ? "DOWNLOAD " : "UPLOAD ", 1, 1, 158, 1);
        design_history(c, key, 1, 13, 158, 20);
        design_value(c, "NET_CONNECTION", "", 1, 36, 158, 0);
        break;
    }
    case 4:
        design_value(c, "NET_DOWN", "DL ", 1, 2, 91, 1);
        design_value(c, "NET_UP", "UL ", 1, 19, 91, 1);
        design_history(c, "NET_DOWN", 100, 1, 59, 18);
        design_history(c, "NET_UP", 100, 23, 59, 18);
        break;
    case 5:
        design_history(c, "NET_DOWN", 1, 1, 62, 19);
        design_history(c, "NET_UP", 1, 23, 62, 19);
        design_value(c, "NET_DOWN", "DL ", 68, 5, 91, 1);
        design_value(c, "NET_UP", "UL ", 68, 27, 91, 1);
        break;
    case 6:
        design_frame(c, 0, 0, 78, 31); design_frame(c, 82, 0, 78, 31);
        design_metric(c, "NET_DOWN", "DOWNLOAD", 3, 3, 72, 25, 1, 0);
        design_metric(c, "NET_UP", "UPLOAD", 85, 3, 72, 25, 1, 0);
        design_value(c, "NET_IPV4", "", 1, 36, 158, 0);
        break;
    case 7:
        design_value(c, "NET_CONNECTION", "", 2, 1, 156, 2);
        design_value(c, "NET_IPV4", "IP ", 2, 14, 156, 1);
        design_value(c, "NET_DOWN", "DL ", 2, 29, 76, 0);
        design_value(c, "NET_UP", "UL ", 83, 29, 75, 0);
        break;
    case 8:
        design_value(c, "NET_CONNECTION", "> ", 1, 1, 158, 0);
        design_value(c, "NET_IPV4", "> IP ", 1, 12, 158, 0);
        design_value(c, "NET_DOWN", "> RX ", 1, 23, 158, 0);
        design_value(c, "NET_UP", "> TX ", 1, 36, 158, 0);
        break;
    case 9:
        design_value(c, "NET_DOWN", "DL ", 1, 0, 158, 0);
        design_history(c, "NET_DOWN", 1, 8, 158, 12);
        design_value(c, "NET_UP", "UL ", 1, 22, 158, 0);
        design_history(c, "NET_UP", 1, 30, 158, 12);
        break;
    case 10:
    case 11:
        design_metric(c, index == 10 ? "NET_DOWN" : "NET_UP",
                      index == 10 ? "DOWNLOAD" : "UPLOAD", 2, 1, 156, 25, 1, 0);
        design_history(c, index == 10 ? "NET_UP" : "NET_DOWN", 2, 26, 76, 15);
        design_value(c, index == 10 ? "NET_UP" : "NET_DOWN",
                      index == 10 ? "UL " : "DL ", 84, 29, 75, 0);
        break;
    case 12:
        design_value(c, "NET_DOWN", "DL ", 2, 5, 156, 3);
        design_value(c, "NET_UP", "UL ", 2, 27, 156, 3);
        break;
    case 13:
        design_history(c, "NET_DOWN", 1, 1, 100, 27);
        design_value(c, "NET_DOWN", "DL ", 105, 3, 54, 0);
        design_value(c, "NET_UP", "UL ", 105, 18, 54, 0);
        design_value(c, "NET_IPV4", "IP ", 1, 36, 158, 0);
        break;
    case 14:
        design_text(c, "LOKALE IP-ADRESSE", 0, 1, 1, 158, 6, 0);
        design_value(c, "NET_IPV4", "", 1, 12, 158, 2);
        design_value(c, "NET_CONNECTION", "", 1, 28, 158, 0);
        design_history(c, "NET_DOWN", 1, 36, 76, 7);
        design_history(c, "NET_UP", 83, 36, 76, 7);
        break;
    case 15:
        design_text(c, "DOWNLOAD", 0, 2, 4, 74, 6, 0);
        design_text(c, "UPLOAD", 0, 84, 4, 74, 6, 0);
        design_value(c, "NET_DOWN", "", 2, 17, 74, 2);
        design_value(c, "NET_UP", "", 84, 17, 74, 2);
        break;
    case 16:
        design_value(c, "NET_DOWN", "DL ", 1, 0, 77, 0);
        design_value(c, "NET_UP", "UL ", 83, 0, 76, 0);
        design_history(c, "NET_DOWN", 1, 10, 158, 12);
        design_history(c, "NET_UP", 1, 24, 158, 12);
        design_value(c, "NET_CONNECTION", "", 1, 37, 158, 0);
        break;
    case 17:
        design_value(c, "NET_DOWN", "DL ", 2, 2, 73, 1);
        design_value(c, "NET_UP", "UL ", 85, 2, 73, 1);
        design_history(c, "NET_DOWN", 2, 17, 73, 24);
        design_history(c, "NET_UP", 85, 17, 73, 24);
        g15r_drawLine(c, 79, 0, 79, 42, G15_COLOR_BLACK);
        break;
    case 18:
        design_frame(c, 0, 0, 160, 43);
        design_value(c, "NET_CONNECTION", "", 3, 2, 154, 0);
        design_value(c, "NET_DOWN", "DL ", 3, 14, 89, 0);
        design_value(c, "NET_UP", "UL ", 3, 27, 89, 0);
        design_history(c, "NET_DOWN", 98, 12, 59, 12);
        design_history(c, "NET_UP", 98, 27, 59, 12);
        break;
    case 19:
        design_history(c, "NET_DOWN", 0, 0, 160, 23);
        design_value(c, "NET_DOWN", "DL ", 1, 26, 77, 0);
        design_value(c, "NET_UP", "UL ", 83, 26, 76, 0);
        design_value(c, "NET_IPV4", "", 1, 37, 158, 0);
        break;
    }
}

typedef struct {
    design_rect_t title, artist, elapsed, visualizer, progress;
    int title_font, artist_font, frame, invert;
} media_design_t;

static const media_design_t media_designs[19] = {
    {{2,1,156,9},{2,12,156,6},{2,22,76,6},{2,32,156,10},{82,22,76,6},1,0,0,0},
    {{58,2,100,9},{58,15,100,6},{58,26,100,6},{1,1,51,41},{58,36,100,6},1,0,0,0},
    {{2,2,100,9},{2,15,100,6},{2,26,100,6},{108,1,51,41},{2,36,100,6},1,0,0,0},
    {{2,3,156,11},{2,19,156,6},{2,33,76,6},{110,29,48,13},{2,27,101,4},3,0,0,0},
    {{2,17,156,9},{2,2,156,11},{2,34,76,6},{111,29,47,13},{2,28,101,4},1,3,0,0},
    {{2,1,156,9},{2,13,156,6},{2,24,156,6},{2,36,156,6},{2,32,156,3},1,0,0,0},
    {{5,4,150,9},{5,15,150,6},{5,30,72,6},{83,26,72,12},{5,24,72,4},1,0,1,0},
    {{3,3,73,9},{3,17,73,6},{3,33,73,6},{84,3,73,28},{84,35,73,5},1,0,2,0},
    {{1,1,158,9},{1,34,90,6},{95,34,64,6},{1,13,158,17},{1,31,158,2},1,0,0,0},
    {{2,1,156,9},{2,12,156,6},{103,23,55,6},{2,23,94,19},{103,34,55,6},1,0,0,0},
    {{2,7,156,10},{2,22,156,6},{2,35,156,6},{0,0,0,0},{2,31,156,2},2,0,0,0},
    {{9,2,149,6},{9,13,149,6},{9,24,149,6},{103,34,55,8},{9,35,87,5},0,0,3,0},
    {{2,1,156,6},{2,10,156,6},{2,36,76,6},{2,19,156,14},{82,36,76,5},0,0,0,0},
    {{2,1,156,9},{2,12,156,6},{2,25,156,11},{112,36,46,6},{2,37,104,4},1,0,0,0},
    {{4,3,152,9},{4,15,152,6},{4,32,70,6},{82,25,74,14},{4,25,70,4},1,0,1,0},
    {{5,4,150,11},{5,18,150,6},{5,34,150,6},{0,0,0,0},{5,27,150,4},3,0,1,0},
    {{3,3,96,9},{3,17,96,6},{3,32,96,6},{107,3,50,36},{3,26,96,3},1,0,2,0},
    {{3,3,154,9},{3,16,154,6},{3,33,72,6},{83,26,74,13},{3,26,72,4},1,0,0,1},
    {{2,1,156,9},{2,29,156,6},{2,37,76,6},{2,12,156,13},{82,37,76,5},1,0,0,0},
};

static void design_visualizer(g15canvas *c, design_rect_t box) {
    g15canvas scratch G15_CANVAS_AUTO = {0};
    g15r_initCanvas(&scratch);
    visualizer_t v = {0, 0, box.w, box.h};
    draw_visualizer_element(&scratch, &v);
    /* The editable visualizer intentionally draws a full-width baseline. */
    for (int y = 0; y < box.h; y++) for (int x = 0; x < box.w; x++)
        if (g15r_getPixel(&scratch, x, y))
            g15r_setPixel(c, box.x + x, box.y + y, G15_COLOR_BLACK);
}

static void design_note(g15canvas *c, int x, int y) {
    g15r_drawLine(c, x + 4, y, x + 4, y + 10, 1);
    g15r_drawLine(c, x + 4, y, x + 8, y + 2, 1);
    g15r_pixelBox(c, x, y + 9, x + 4, y + 11, 1, 1, 1);
}

static void design_media_animation_frame(g15canvas *c, int index, double seconds) {
    g15canvas scene G15_CANVAS_AUTO = {0};
    g15r_initCanvas(&scene);
    int tick = (int)(seconds * 12);
    switch (index) {
    case 1: /* Floating notes. */
        for (int i = 0; i < 8; i++)
            design_note(&scene, (i * 23 + tick * 2) % 180 - 10,
                         5 + 5 * sin(seconds * 2 + i));
        break;
    case 2: /* Rotating record. */
        for (int r = 3; r <= 11; r += 4) g15r_drawCircle(&scene, 80, 12, r, 0, 1);
        for (int i = 0; i < 3; i++) {
            double a = seconds * 2 + i * 2 * M_PI / 3;
            g15r_drawLine(&scene, 80 + cos(a) * 5, 12 + sin(a) * 5,
                          80 + cos(a) * 10, 12 + sin(a) * 10, 1);
        }
        g15r_drawLine(&scene, 108, 2, 98, 2, 1);
        g15r_drawLine(&scene, 98, 2, 88, 14, 1);
        break;
    case 3: /* Scrolling film strip. */
        for (int i = 0; i < 7; i++) {
            int x = i * 28 - tick * 2 % 28;
            design_frame(&scene, x, 1, 26, 23);
            design_frame(&scene, x + 3, 6, 20, 13);
            for (int dx = 3; dx < 24; dx += 6) {
                design_frame(&scene, x + dx, 2, 3, 3);
                design_frame(&scene, x + dx, 20, 3, 3);
            }
        }
        break;
    case 4: /* Two cassette reels. */
        design_frame(&scene, 38, 1, 84, 23);
        for (int reel = 0; reel < 2; reel++) {
            int x = 57 + reel * 46;
            g15r_drawCircle(&scene, x, 12, 8, 0, 1);
            for (int spoke = 0; spoke < 3; spoke++) {
                double a = seconds * (reel ? -2 : 2) + spoke * 2 * M_PI / 3;
                g15r_drawLine(&scene, x, 12, x + cos(a) * 6, 12 + sin(a) * 6, 1);
            }
        }
        g15r_drawLine(&scene, 65, 17, 95, 17, 1);
        break;
    case 5: /* Travelling piano key press. */
        for (int i = 0; i < 20; i++) {
            design_frame(&scene, i * 8, 3, 8, 21);
            if (i % 7 != 2 && i % 7 != 6)
                g15r_pixelBox(&scene, i * 8 + 5, 3, i * 8 + 8, 13, 1, 1, 1);
            if (i == tick % 20)
                g15r_pixelBox(&scene, i * 8 + 2, 16, i * 8 + 5, 21, 1, 1, 1);
        }
        break;
    case 6: /* Expanding speaker ripples. */
        design_frame(&scene, 72, 2, 16, 21);
        g15r_drawCircle(&scene, 80, 15, 5, 0, 1);
        g15r_drawCircle(&scene, 80, 6, 2, 0, 1);
        for (int i = 0; i < 4; i++) {
            int distance = 12 + (tick + i * 11) % 60;
            for (int y = 2; y < 24; y++) {
                int bend = abs(y - 12) / 3;
                g15r_setPixel(&scene, 80 - distance + bend, y, 1);
                g15r_setPixel(&scene, 80 + distance - bend, y, 1);
            }
        }
        break;
    case 7: /* Pendulum metronome. */
        g15r_drawLine(&scene, 65, 24, 80, 1, 1);
        g15r_drawLine(&scene, 80, 1, 95, 24, 1);
        g15r_drawLine(&scene, 65, 24, 95, 24, 1);
        g15r_drawLine(&scene, 80, 22, 80 + sin(seconds * 4) * 20, 3, 1);
        design_frame(&scene, 77 + sin(seconds * 4) * 12, 10, 6, 4);
        break;
    case 8: /* Decorative sine ribbon, not measured audio. */
        for (int x = 0; x < 160; x++) {
            int y = 12 + 9 * sin(x * .07 - seconds * 3);
            g15r_setPixel(&scene, x, y, 1);
            g15r_setPixel(&scene, x, 24 - y, 1);
        }
        break;
    case 9: /* Bouncing play symbol. */
        {
            int x = 10 + (int)(seconds * 22) % 270;
            if (x > 145) x = 290 - x;
            for (int i = 0; i < 12; i++)
                g15r_drawLine(&scene, x + i, 2 + i, x + i, 24 - i, 1);
        }
        break;
    case 10: /* Rotating CD. */
        g15r_drawCircle(&scene, 80, 12, 11, 0, 1);
        g15r_drawCircle(&scene, 80, 12, 3, 0, 1);
        for (int i = 0; i < 5; i++) {
            double a = seconds * 1.5 + i * .15;
            for (int side = -1; side <= 1; side += 2)
                g15r_drawLine(&scene, 80 + side * cos(a) * 5, 12 + side * sin(a) * 5,
                              80 + side * cos(a) * 10, 12 + side * sin(a) * 10, 1);
        }
        break;
    case 11: /* Music staff with travelling notes. */
        for (int y = 5; y <= 21; y += 4) g15r_drawLine(&scene, 0, y, 159, y, 1);
        for (int i = 0; i < 6; i++)
            design_note(&scene, (i * 29 + 320 - tick * 2 % 174) % 174 - 10,
                         (i * 3 % 5) * 2);
        break;
    case 12: /* Clapperboard. */
        design_frame(&scene, 53, 10, 54, 14);
        int lift = (int)lround(8 * (1 + sin(seconds * 3)));
        g15r_drawLine(&scene, 53, 9, 106, 9 - lift, 1);
        g15r_drawLine(&scene, 53, 5, 106, 5 - lift, 1);
        for (int i = 0; i < 7; i++) {
            int x = 54 + i * 8, y = 5 - lift * (x - 53) / 53;
            g15r_drawLine(&scene, x, y, x + 4, y + 3, 1);
        }
        break;
    case 13: /* Projector reel. */
        for (int reel = 0; reel < 2; reel++) {
            int x = 63 + reel * 28;
            g15r_drawCircle(&scene, x, 8, 7, 0, 1);
            for (int i = 0; i < 4; i++) {
                double a = seconds * 2 + i * M_PI / 2;
                g15r_drawCircle(&scene, x + cos(a) * 4, 8 + sin(a) * 4, 1, 1, 1);
            }
        }
        design_frame(&scene, 58, 15, 42, 9);
        g15r_drawLine(&scene, 100, 16, 125 + tick % 8, 10, 1);
        g15r_drawLine(&scene, 100, 22, 125 + tick % 8, 24, 1);
        break;
    case 14: /* Orbiting notes. */
        for (int i = 0; i < 5; i++) {
            double a = seconds * 1.3 + i * 2 * M_PI / 5;
            design_note(&scene, 76 + cos(a) * 62, 6 + sin(a) * 6);
        }
        break;
    case 15: /* Headphones with pulsing ear cups. */
        for (int i = 0; i <= 32; i++) {
            double a = M_PI + i * M_PI / 32;
            g15r_setPixel(&scene, 80 + cos(a) * 22, 18 + sin(a) * 16, 1);
        }
        for (int side = -1; side <= 1; side += 2) {
            int x = 77 + side * 21;
            design_frame(&scene, x, 13, 7, 11);
            int h = 2 + (int)lround(4 * (1 + sin(seconds * 4 + side * .7)));
            g15r_drawLine(&scene, x + 3, 23 - h, x + 3, 22, 1);
        }
        break;
    case 16: /* Scanning radio dial. */
        design_frame(&scene, 20, 3, 120, 19);
        for (int x = 26; x < 137; x += 6)
            g15r_drawLine(&scene, x, 5, x, x % 12 ? 9 : 12, 1);
        int x = 26 + (int)(54 * (1 + sin(seconds * 1.4)));
        g15r_drawLine(&scene, x, 4, x, 20, 1);
        break;
    case 17: /* Flowing tape loops. */
        for (int x = 0; x < 160; x++) {
            double phase = x * .065 + seconds * 2;
            int y = 12 + 8 * sin(phase) * cos(phase * .5);
            g15r_setPixel(&scene, x, y, 1);
            g15r_setPixel(&scene, x, y + 2, 1);
        }
        break;
    case 18: /* Decorative dancing tiles, not an audio meter. */
        for (int i = 0; i < 18; i++) {
            int y = 10 + 8 * sin(seconds * 3 + i * .6);
            design_frame(&scene, i * 9 + 1, y, 6, 6);
        }
        break;
    case 19: /* Musical shooting stars. */
        for (int i = 0; i < 5; i++) {
            int x = (tick * 3 + i * 37) % 190 - 15, y = i * 3;
            design_note(&scene, x, y);
            for (int trail = 6; trail < 20; trail += 4)
                g15r_setPixel(&scene, x - trail, y + 10, 1);
        }
        break;
    }
    draw_fullscreen_animation(c, &scene, 0, 25);
}

static void design_media(g15canvas *c, int index) {
    if (!g_media_title[0] || g_media_is_game) {
        struct timespec now;
        clock_gettime(CLOCK_MONOTONIC, &now);
        design_media_animation_frame(c, index, fmod(now.tv_sec + now.tv_nsec / 1e9, 120));
        g_marquee_active = 1;
        return;
    }
    const media_design_t *d = &media_designs[index - 1];
    int has_media = g_media_title[0] && !g_media_is_game;
    int playing = has_media && g_media_playing;
    const char *title = has_media ? g_media_title : "Keine Wiedergabe";
    const char *artist = has_media ? g_media_artist : "MEDIA CENTER";
    if (d->frame == 1) design_frame(c, 0, 0, 160, 43);
    if (d->frame == 2) g15r_drawLine(c, 79 + (index == 17 ? 24 : 0), 0,
                                     79 + (index == 17 ? 24 : 0), 42, G15_COLOR_BLACK);
    if (d->frame == 3) {
        design_text(c, ">", 0, 1, 2, 6, 6, 0);
        design_text(c, ">", 0, 1, 13, 6, 6, 0);
    }
    if (has_media) {
        if (!draw_marquee_text(c, title, d->title_font, d->title.x, d->title.y, d->title.w))
            design_text(c, title, d->title_font, d->title.x, d->title.y, d->title.w, d->title.h, 0);
        if (!draw_marquee_text(c, artist, d->artist_font, d->artist.x, d->artist.y, d->artist.w))
            design_text(c, artist, d->artist_font, d->artist.x, d->artist.y, d->artist.w, d->artist.h, 0);
    } else {
        design_text(c, title, d->title_font, d->title.x, d->title.y, d->title.w, d->title.h, 0);
        design_text(c, artist, d->artist_font, d->artist.x, d->artist.y, d->artist.w, d->artist.h, 0);
    }
    design_text(c, has_media ? g_media_elapsed : "BEREIT",
                 index == 14 ? G15_TEXT_HUGE : G15_TEXT_SMALL, d->elapsed.x, d->elapsed.y,
                 d->elapsed.w, d->elapsed.h, 0);
    if (d->progress.w)
        design_bar(c, has_media ? g_media_progress_pct : -1, d->progress.x,
                    d->progress.y, d->progress.w, d->progress.h);
    if (d->visualizer.w) {
        if (playing) {
            design_visualizer(c, d->visualizer);
            g_marquee_active = 1;
        } else {
            int mid = d->visualizer.y + d->visualizer.h / 2;
            g15r_drawLine(c, d->visualizer.x, mid, d->visualizer.x + d->visualizer.w - 1,
                          mid, G15_COLOR_BLACK);
        }
    }
    if (d->invert)
        for (int y = 0; y < 43; y++) for (int x = 0; x < 160; x++)
            g15r_setPixel(c, x, y, !g15r_getPixel(c, x, y));
}

typedef struct {
    design_rect_t logo;
    const char *left_sensor, *right_sensor;
    int frame, caption, invert;
} game_design_t;

static const game_design_t game_designs[19] = {
    {{3,3,154,37},NULL,NULL,1,0,0},
    {{1,9,158,25},NULL,NULL,2,0,0},
    {{2,2,108,39},"CPU_TEMP","GPU_EDGE_TEMP",3,0,0},
    {{50,2,108,39},"CPU_PCT","GPU_PCT",4,0,0},
    {{2,1,156,29},NULL,NULL,0,1,0},
    {{2,1,156,28},"CPU_TEMP","GPU_EDGE_TEMP",5,0,0},
    {{2,1,156,28},"CPU_PCT","GPU_PCT",5,0,0},
    {{3,3,99,37},"RAM_PCT","VRAM_PCT",3,0,0},
    {{3,12,154,28},NULL,NULL,1,2,0},
    {{4,4,152,35},NULL,NULL,0,0,1},
    {{9,4,142,35},NULL,NULL,6,0,0},
    {{4,10,152,23},NULL,NULL,7,0,0},
    {{42,3,76,27},"CPU_TEMP","GPU_EDGE_TEMP",5,0,0},
    {{2,2,101,27},"CPU_PCT","RAM_PCT",8,0,0},
    {{2,2,101,27},"NET_DOWN","NET_UP",8,0,0},
    {{2,2,101,27},"RAM_PCT","VRAM_PCT",8,0,0},
    {{1,12,158,19},NULL,NULL,2,1,0},
    {{3,3,154,27},"GPU_PCT","GPU_EDGE_TEMP",1,0,0},
    {{3,12,104,28},"CPU_TEMP","GPU_EDGE_TEMP",9,2,0},
};

static void design_game_logo(g15canvas *c, design_rect_t box) {
    g15canvas logo G15_CANVAS_AUTO = {0};
    g15r_initCanvas(&logo);
    int width = 160, height = 43;
    if (g_media_is_game && g_game_logo_active) {
        image_t image = g_game_logo;
        image.x = image.y = 0;
        width = image.width; height = image.height;
        draw_image_element(&logo, &image);
    } else if (g_media_is_game && g_game_title_active) {
        width = g_game_title_width;
        height = g_game_title_line_count * g_game_title_line_height - 1;
        for (int i = 0; i < g_game_title_line_count; i++)
            g15r_renderString(&logo, (unsigned char *)g_game_title_lines[i], 0,
                              g_game_title_font, 0, i * g_game_title_line_height);
    } else {
        design_text(&logo, g_media_is_game ? "SPIEL AKTIV" : "Ready to rumble",
                     G15_TEXT_HUGE, 0, 0, 160, 12, 0);
        width = measure_builtin_text_width(g_media_is_game ? "SPIEL AKTIV" : "Ready to rumble",
                                           G15_TEXT_HUGE);
        height = 12;
    }
    if (width < 1 || height < 1) return;
    double scale = fmin((double)box.w / width, (double)box.h / height);
    int w = fmax(1, floor(width * scale)), h = fmax(1, floor(height * scale));
    int x0 = box.x + (box.w - w) / 2, y0 = box.y + (box.h - h) / 2;
    for (int y = 0; y < h; y++) for (int x = 0; x < w; x++)
        if (g15r_getPixel(&logo, x * width / w, y * height / h))
            g15r_setPixel(c, x0 + x, y0 + y, G15_COLOR_BLACK);
}

static void arcade_block(g15canvas *c, int x, int y, int size) {
    design_frame(c, x, y, size, size);
    if (size >= 5) g15r_setPixel(c, x + 2, y + 2, 1);
}

static void arcade_person(g15canvas *c, int x, int y, int stride) {
    g15r_drawCircle(c, x, y, 2, 0, 1);
    g15r_drawLine(c, x, y + 2, x, y + 7, 1);
    g15r_drawLine(c, x - 3, y + 4, x + 3, y + 4, 1);
    g15r_drawLine(c, x, y + 7, x - stride, y + 10, 1);
    g15r_drawLine(c, x, y + 7, x + stride, y + 10, 1);
}

static void arcade_portal_cube(g15canvas *c, double phase) {
    /* Disappear into the right wall, then emerge from the left wall. */
    int x = (int)lround(phase < 2 ? 96 + phase * 26 : 8 + (phase - 2) * 44);
    for (int y = 17; y <= 25; y++) for (int dx = 0; dx < 9; dx++) {
        int px = x + dx;
        if (px <= 17 || px >= 143) continue;
        if (y == 17 || y == 25 || dx == 0 || dx == 8 ||
            (dx == 4 && y >= 20 && y <= 22))
            g15r_setPixel(c, px, y, 1);
    }
}

static void design_game_animation_frame(g15canvas *c, int index, double seconds) {
    g15canvas scene G15_CANVAS_AUTO = {0};
    g15r_initCanvas(&scene);
    int tick = (int)(seconds * 12);
    switch (index) {
    case 1: { /* Falling I-piece completes four rows, which then disappear. */
        double phase = fmod(seconds, 4);
        design_frame(&scene, 58, 0, 44, 43);
        for (int row = 0; row < 4; row++) for (int col = 0; col < 10; col++)
            if (phase < 3 && col != 6)
                arcade_block(&scene, 60 + col * 4, 25 + row * 4, 4);
        if (phase < 3) {
            int y = phase < 2.5 ? 1 + (int)(phase / 2.5 * 24) : 25;
            for (int row = 0; row < 4; row++)
                arcade_block(&scene, 84, y + row * 4, 4);
        } else {
            int y = (phase - 3) * 12;
            for (int col = 0; col < 3; col++) arcade_block(&scene, 72 + col * 4, y, 4);
            arcade_block(&scene, 76, y + 4, 4);
        }
        design_frame(&scene, 112, 6, 25, 25);
        for (int i = 0; i < 3; i++) arcade_block(&scene, 118 + i * 4, 13, 4);
        arcade_block(&scene, 122, 17, 4);
        for (int i = 0; i < 3; i++) arcade_block(&scene, 27, 12 + i * 5, 5);
        break;
    }
    case 2: { /* A point-eating disc and two original pursuer sprites. */
        design_frame(&scene, 0, 0, 160, 43);
        for (int i = 0; i < 5; i++) {
            design_frame(&scene, 12 + i * 29, 6, 20, 9);
            design_frame(&scene, 12 + i * 29, 29, 20, 8);
        }
        int x = 8 + tick * 2 % 144;
        for (int dot = 8; dot < 155; dot += 7)
            if (dot > x + 6) g15r_pixelBox(&scene, dot, 21, dot + 1, 22, 1, 1, 1);
        for (int dy = -5; dy <= 5; dy++) for (int dx = -5; dx <= 5; dx++)
            if (dx * dx + dy * dy <= 25 &&
                !(dx > 0 && abs(dy) <= dx * ((tick % 4) + 1) / 4))
                g15r_setPixel(&scene, x + dx, 22 + dy, 1);
        for (int i = 0; i < 2; i++) {
            int gx = 6 + (x + 110 - i * 16) % 146;
            g15r_drawCircle(&scene, gx, 21, 4, 1, 1);
            g15r_pixelBox(&scene, gx - 4, 21, gx + 4, 25, 1, 1, 1);
            g15r_setPixel(&scene, gx - 2, 21, 0);
            g15r_setPixel(&scene, gx + 2, 21, 0);
            for (int j = -3; j <= 3; j += 3)
                g15r_setPixel(&scene, gx + j, 25 + (tick % 2), 1);
        }
        break;
    }
    case 3: { /* Portals are fixed wall openings; the cube really changes sides. */
        design_frame(&scene, 0, 0, 160, 43);
        for (int side = 0; side < 2; side++) {
            int cx = side ? 143 : 17;
            g15r_drawLine(&scene, cx, 1, cx, 8, 1);
            g15r_drawLine(&scene, cx, 34, cx, 41, 1);
            for (int i = 0; i < 96; i++) {
                double a = i * M_PI / 48;
                g15r_setPixel(&scene, cx + cos(a) * 5, 21 + sin(a) * 13, 1);
                if ((i + tick) % 12 < 6)
                    g15r_setPixel(&scene, cx + cos(a) * 7, 21 + sin(a) * 15, 1);
            }
        }
        arcade_portal_cube(&scene, fmod(seconds, 4));
        g15r_drawLine(&scene, 18, 35, 142, 35, 1);
        design_frame(&scene, 72, 32, 16, 4);
        break;
    }
    case 4: {
        double phase = fmod(seconds * .7, 2);
        double travel = phase < 1 ? phase : 2 - phase;
        int x = 9 + travel * 140, y = 7 + 27 * (.5 + .5 * sin(seconds * 2.3));
        for (int row = 2; row < 41; row += 5) g15r_drawLine(&scene, 80, row, 80, row + 2, 1);
        g15r_pixelBox(&scene, 3, clamp_int(y - 6, 1, 28), 5, clamp_int(y - 6, 1, 28) + 12, 1, 1, 1);
        g15r_pixelBox(&scene, 154, clamp_int(y - 6, 1, 28), 156, clamp_int(y - 6, 1, 28) + 12, 1, 1, 1);
        g15r_pixelBox(&scene, x, y, x + 2, y + 2, 1, 1, 1);
        break;
    }
    case 5: { /* Brick wall gradually loses bricks while a ball bounces. */
        int removed = (int)(seconds * 2) % 25;
        for (int row = 0; row < 3; row++) for (int col = 0; col < 12; col++)
            if (row * 12 + col >= removed)
                design_frame(&scene, 3 + col * 13, 1 + row * 6, 11, 5);
        int x = 8 + (int)(70 * (1 + sin(seconds * 1.8)));
        int y = 19 + fabs(sin(seconds * 3)) * 17;
        g15r_drawCircle(&scene, x, y, 2, 1, 1);
        g15r_pixelBox(&scene, clamp_int(x - 10, 1, 137), 39,
                      clamp_int(x - 10, 1, 137) + 21, 41, 1, 1, 1);
        break;
    }
    case 6: { /* Grid snake grows towards food and turns around the field. */
        design_frame(&scene, 0, 0, 160, 43);
        int head = tick % 80, length = head < 24 ? 9 : 12;
        for (int i = 0; i < length; i++) {
            int p = (head + 80 - i) % 80;
            int x = p < 35 ? p : p < 40 ? 35 : p < 75 ? 75 - p : 0;
            int y = p < 35 ? 0 : p < 40 ? p - 35 : p < 75 ? 5 : 80 - p;
            g15r_pixelBox(&scene, 8 + x * 4, 10 + y * 4, 10 + x * 4, 12 + y * 4, 1, 1, 1);
        }
        if (head < 24) g15r_drawCircle(&scene, 104, 10, 2, 0, 1);
        break;
    }
    case 7: /* Crossing traffic and a river on moving logs. */
        for (int lane = 0; lane < 4; lane++) {
            int y = 5 + lane * 9;
            for (int i = 0; i < 4; i++) {
                int x = (i * 46 + tick * (lane % 2 ? 2 : 3)) % 184 - 20;
                design_frame(&scene, x, y, lane < 2 ? 26 : 15, 6);
                if (lane < 2) g15r_drawLine(&scene, x + 3, y + 3, x + 22, y + 3, 1);
                else {
                    g15r_setPixel(&scene, x + 3, y + 6, 1);
                    g15r_setPixel(&scene, x + 11, y + 6, 1);
                }
            }
        }
        {
            int y = 38 - (tick % 36), x = 80 + (int)(4 * sin(seconds * 3));
            design_frame(&scene, x - 2, y, 5, 4);
            for (int side = -1; side <= 1; side += 2) {
                g15r_drawLine(&scene, x + side * 2, y, x + side * 4, y - 2, 1);
                g15r_drawLine(&scene, x + side * 2, y + 3, x + side * 4, y + 5, 1);
            }
        }
        break;
    case 8: { /* Tile maze, timed bomb and a cross-shaped blast. */
        for (int row = 0; row < 4; row++) for (int col = 0; col < 14; col++)
            if ((row % 2 == 0 && col % 2 == 0) || (row == 3 && col % 3 == 0))
                arcade_block(&scene, 3 + col * 11, 2 + row * 11, 8);
        double phase = fmod(seconds, 4);
        int x = 44 + (int)(phase * 14);
        arcade_person(&scene, x, 16, 1 + tick % 3);
        if (phase < 3) {
            g15r_drawCircle(&scene, 40, 29, 4, 1, 1);
            g15r_drawLine(&scene, 40, 24, 43 + tick % 3, 22, 1);
        } else {
            g15r_pixelBox(&scene, 23, 27, 57, 31, 1, 1, 1);
            g15r_pixelBox(&scene, 38, 13, 42, 41, 1, 1, 1);
        }
        break;
    }
    case 9: { /* Rotating triangle ship, polygon rocks and a moving shot. */
        for (int rock = 0; rock < 6; rock++) {
            int cx = (rock * 31 + tick) % 180 - 10, cy = 7 + rock * 7 % 30;
            for (int i = 0; i < 7; i++) {
                double a = i * 2 * M_PI / 7, b = (i + 1) * 2 * M_PI / 7;
                int r = 4 + (i + rock) % 3, nr = 4 + (i + 1 + rock) % 3;
                g15r_drawLine(&scene, cx + cos(a) * r, cy + sin(a) * r,
                              cx + cos(b) * nr, cy + sin(b) * nr, 1);
            }
        }
        double a = seconds * 1.5;
        int nx = 80 + cos(a) * 10, ny = 21 + sin(a) * 10;
        g15r_drawLine(&scene, nx, ny, 80 + cos(a + 2.5) * 7, 21 + sin(a + 2.5) * 7, 1);
        g15r_drawLine(&scene, nx, ny, 80 + cos(a - 2.5) * 7, 21 + sin(a - 2.5) * 7, 1);
        g15r_drawLine(&scene, 80 + cos(a + 2.5) * 7, 21 + sin(a + 2.5) * 7,
                      80 + cos(a - 2.5) * 7, 21 + sin(a - 2.5) * 7, 1);
        int distance = 14 + tick * 3 % 55;
        g15r_drawCircle(&scene, 80 + cos(a) * distance, 21 + sin(a) * distance, 1, 1, 1);
        break;
    }
    case 10: { /* A worker pushes a crate onto a marked target. */
        design_frame(&scene, 18, 1, 124, 41);
        for (int x = 20; x < 140; x += 12) {
            arcade_block(&scene, x, 2, 10);
            arcade_block(&scene, x, 31, 10);
        }
        double phase = fmod(seconds, 5);
        int x = 44 + fmin(phase, 4) * 16;
        g15r_drawCircle(&scene, 112, 23, 4, 0, 1);
        design_frame(&scene, x, 18, 10, 10);
        g15r_drawLine(&scene, x, 18, x + 9, 27, 1);
        g15r_drawLine(&scene, x, 27, x + 9, 18, 1);
        arcade_person(&scene, x - 6, 16, 1 + tick % 3);
        if (phase >= 4) design_frame(&scene, 108, 17, 12, 12);
        break;
    }
    case 11: { /* Revealed minefield cells, flags and a travelling pointer. */
        int revealed = (int)(seconds * 3) % 48;
        for (int row = 0; row < 4; row++) for (int col = 0; col < 16; col++) {
            int x = col * 10, y = row * 10 + 1, cell = row * 16 + col;
            design_frame(&scene, x, y, 10, 10);
            if (cell < revealed) {
                int dots = (col + row) % 3 + 1;
                for (int d = 0; d < dots; d++)
                    g15r_pixelBox(&scene, x + 3 + d * 2, y + 4, x + 3 + d * 2, y + 5, 1, 1, 1);
            } else if (cell % 13 == 0) {
                g15r_drawLine(&scene, x + 3, y + 2, x + 3, y + 7, 1);
                g15r_pixelBox(&scene, x + 4, y + 2, x + 7, y + 4, 1, 1, 1);
            } else {
                g15r_drawLine(&scene, x + 2, y + 2, x + 7, y + 2, 1);
            }
        }
        int x = tick * 3 % 148, y = 14 + 10 * sin(seconds * 2);
        g15r_drawLine(&scene, x, y, x + 5, y + 5, 1);
        g15r_drawLine(&scene, x, y, x, y + 8, 1);
        break;
    }
    case 12: { /* Pinball bumpers, moving ball and paired flippers. */
        design_frame(&scene, 17, 0, 126, 43);
        for (int i = 0; i < 5; i++)
            g15r_drawCircle(&scene, 38 + i * 21, 10 + i % 2 * 9, 4, 0, 1);
        int lift = lround(4 * sin(seconds * 5));
        g15r_drawLine(&scene, 47, 35, 72, 36 + lift, 1);
        g15r_drawLine(&scene, 112, 35, 87, 36 - lift, 1);
        int x = 26 + 106 * (.5 + .5 * sin(seconds * 2.1));
        int y = 5 + fabs(sin(seconds * 3.7)) * 26;
        g15r_drawCircle(&scene, x, y, 2, 1, 1);
        g15r_drawLine(&scene, 20, 23, 37, 35, 1);
        g15r_drawLine(&scene, 139, 23, 122, 35, 1);
        break;
    }
    case 13: /* Platform runner and scrolling obstacles. */
        {
            int jump = fabs(sin(seconds * 2.7)) * 14;
            arcade_person(&scene, 42, 27 - jump, 1 + tick % 3);
            for (int i = 0; i < 6; i++) {
                int x = (i * 34 + 204 - tick * 2 % 204) % 204 - 20;
                design_frame(&scene, x, 38, 27, 5);
                if (i % 2) {
                    arcade_block(&scene, x + 15, 29, 9);
                    arcade_block(&scene, x + 10, 7, 8);
                    g15r_drawCircle(&scene, x + 14, 3, 2, 0, 1);
                }
            }
        }
        break;
    case 14: /* Arcade formation of original pixel drones. */
        for (int row = 0; row < 3; row++) for (int column = 0; column < 8; column++) {
            int x = 9 + column * 18 + sin(seconds * 2) * 6, y = row * 9 + 2;
            design_frame(&scene, x, y + 1, 8, 4);
            g15r_setPixel(&scene, x + 2, y, 1);
            g15r_setPixel(&scene, x + 5, y, 1);
            int leg = (tick / 2 + row) % 2;
            g15r_drawLine(&scene, x + leg, y + 5, x + leg + 1, y + 6, 1);
            g15r_drawLine(&scene, x + 6 - leg, y + 5, x + 7 - leg, y + 6, 1);
        }
        {
            int x = 12 + tick * 2 % 133;
            g15r_drawLine(&scene, x - 6, 41, x, 34, 1);
            g15r_drawLine(&scene, x, 34, x + 6, 41, 1);
            g15r_drawLine(&scene, x - 6, 41, x + 6, 41, 1);
            int y = 33 - tick * 3 % 30;
            g15r_drawLine(&scene, x, y, x, y + 3, 1);
        }
        break;
    case 15: /* Mining blocks with a visibly swinging pickaxe. */
        for (int row = 0; row < 4; row++) for (int col = 0; col < 8; col++) {
            if (row == 1 && col == 0 && fmod(seconds, 3) > 2) continue;
            arcade_block(&scene, 80 + col * 10, 2 + row * 10, 10);
            if (row == 1 && col == 0) {
                int crack = (int)(fmod(seconds, 3) * 3);
                g15r_drawLine(&scene, 83, 13, 84 + crack, 16, 1);
                g15r_drawLine(&scene, 84 + crack, 16, 82, 19, 1);
            }
        }
        {
            double angle = -.6 + sin(seconds * 5) * .9;
            int x = 62 + cos(angle) * 14, y = 22 + sin(angle) * 14;
            arcade_person(&scene, 49, 22, 2);
            g15r_drawLine(&scene, 56, 30, x, y, 1);
            g15r_drawLine(&scene, x - 5, y - 3, x + 6, y + 2, 1);
            for (int i = 0; i < 4; i++)
                g15r_setPixel(&scene, 70 + (tick + i * 3) % 10, 24 + (tick * 2 + i * 4) % 17, 1);
        }
        break;
    case 16: /* Rhythm lanes: descending notes meet a strum line. */
        for (int lane = 0; lane < 5; lane++) {
            int x = 30 + lane * 24;
            g15r_drawLine(&scene, x, 1, x, 41, 1);
            g15r_drawCircle(&scene, x, 35, 5, 0, 1);
            for (int i = 0; i < 3; i++) {
                int y = (tick * 2 + lane * 11 + i * 17) % 52 - 8;
                g15r_pixelBox(&scene, x - 3, y, x + 3, y + 2, 1, 1, 1);
            }
        }
        g15r_drawLine(&scene, 15, 35, 143, 35, 1);
        break;
    case 17: /* Retro road racing. */
        {
            int bend = sin(seconds * .9) * 20;
            g15r_drawLine(&scene, 78 + bend, 2, 15, 42, 1);
            g15r_drawLine(&scene, 82 + bend, 2, 145, 42, 1);
            for (int i = 0; i < 7; i++) {
                double depth = fmod(seconds * .6 + i / 7.0, 1);
                int y = 3 + depth * depth * 36, x = 80 + bend * (42 - y) / 42;
                g15r_drawLine(&scene, x, y, x, y + 1 + depth * 2, 1);
                g15r_setPixel(&scene, 80 - (y - 2) * 2, y, 1);
                g15r_setPixel(&scene, 80 + (y - 2) * 2, y, 1);
            }
            design_frame(&scene, 67, 32, 27, 10);
            design_frame(&scene, 73, 28, 15, 7);
            g15r_pixelBox(&scene, 64, 34, 67, 41, 1, 1, 1);
            g15r_pixelBox(&scene, 94, 34, 97, 41, 1, 1, 1);
            int opponent = 8 + tick % 20;
            design_frame(&scene, 103 - opponent / 2, opponent, 8 + opponent / 3, 5);
        }
        break;
    case 18: /* Dungeon explorer with shield, sword and torchlight. */
        design_frame(&scene, 50, 2, 60, 41);
        design_frame(&scene, 57, 6, 46, 37);
        for (int y = 0; y < 43; y += 6)
            for (int x = 0; x < 160; x += 20) {
                if (x >= 40 && x < 120) continue;
                design_frame(&scene, x + (y % 12 ? -10 : 0), y, 20, 6);
            }
        for (int side = -1; side <= 1; side += 2) {
            int x = 80 + side * 42;
            g15r_drawLine(&scene, x, 18, x, 28, 1);
            for (int i = 0; i < 4; i++) {
                int y = 6 + (tick + i * 3) % 11;
                g15r_drawLine(&scene, x - 2 + sin(seconds * 7 + i) * 2, y,
                              x + 2, y + 2, 1);
            }
        }
        {
            int x = 72 + (int)(5 * sin(seconds * 1.5));
            arcade_person(&scene, x, 26, 1 + tick % 3);
            design_frame(&scene, x - 7, 29, 5, 7);
            g15r_drawLine(&scene, x + 4, 31, x + 13, 24 + (tick % 4), 1);
        }
        break;
    case 19: /* A procession builds and crosses a staircase to the exit. */
        design_frame(&scene, 0, 1, 15, 13);
        design_frame(&scene, 144, 5, 16, 28);
        g15r_drawLine(&scene, 0, 36, 62, 36, 1);
        for (int i = 0; i < 10; i++) {
            g15r_drawLine(&scene, 62 + i * 8, 36 - i * 2, 70 + i * 8, 36 - i * 2, 1);
            g15r_drawLine(&scene, 70 + i * 8, 36 - i * 2, 70 + i * 8, 34 - i * 2, 1);
        }
        for (int i = 0; i < 7; i++) {
            int x = (tick * 2 + i * 24) % 150;
            int foot = x < 62 ? 36 : 36 - (x - 62) / 8 * 2;
            arcade_person(&scene, x, foot - 10, 1 + (tick + i) % 2);
        }
        break;
    }
    draw_fullscreen_animation(c, &scene, 0, 43);
}

static void design_games(g15canvas *c, int index) {
    if (!g_media_is_game) {
        struct timespec now;
        clock_gettime(CLOCK_MONOTONIC, &now);
        double seconds = fmod(now.tv_sec + now.tv_nsec / 1e9, 120);
        design_game_animation_frame(c, index, seconds);
        g_marquee_active = 1;
        return;
    }
    const game_design_t *d = &game_designs[index - 1];
    design_game_logo(c, d->logo);
    switch (d->frame) {
    case 1: design_frame(c, 0, 0, 160, 43); break;
    case 2:
        g15r_drawLine(c, 0, 6, 159, 6, G15_COLOR_BLACK);
        g15r_drawLine(c, 0, 36, 159, 36, G15_COLOR_BLACK); break;
    case 3: g15r_drawLine(c, 113, 0, 113, 42, G15_COLOR_BLACK); break;
    case 4: g15r_drawLine(c, 46, 0, 46, 42, G15_COLOR_BLACK); break;
    case 5: g15r_drawLine(c, 0, 30, 159, 30, G15_COLOR_BLACK); break;
    case 6:
        for (int side = 0; side < 2; side++) {
            int x = side ? 154 : 5;
            g15r_drawLine(c, x, 11, x, 31, G15_COLOR_BLACK);
            g15r_drawLine(c, side ? 145 : 5, 6, side ? 154 : 14, 6, G15_COLOR_BLACK);
            g15r_drawLine(c, side ? 145 : 5, 36, side ? 154 : 14, 36, G15_COLOR_BLACK);
        } break;
    case 7:
        for (int x = 1; x < 160; x += 8) {
            design_frame(c, x, 1, 5, 4); design_frame(c, x, 38, 5, 4);
        } break;
    case 8:
        design_frame(c, 0, 0, 105, 32);
        design_value(c, "TIME", "", 2, 36, 101, 0); break;
    case 9:
        design_text(c, ">", 0, 1, 1, 8, 6, 0);
        g15r_drawLine(c, 110, 11, 110, 42, G15_COLOR_BLACK); break;
    }
    if (d->caption) design_text(c, g_media_is_game ? "SPIEL AKTIV" : "GAMING - BEREIT",
                                0, d->caption == 2 ? 12 : 2,
                                d->caption == 2 ? 2 : 36,
                                d->caption == 2 ? 144 : 156, 6, 0);
    if (d->left_sensor) {
        int left = 2, right = 83, y1 = 34, y2 = 34, w = 75;
        if (d->frame == 3 || d->frame == 4 || d->frame == 8 || d->frame == 9) {
            left = right = d->frame == 4 ? 1 : (d->frame == 3 ? 117 : 114);
            y1 = 5; y2 = 25; w = d->frame == 4 ? 42 : 44;
        }
        const char *label1 = !strncmp(d->left_sensor, "NET_", 4) ? "DL " :
                            !strncmp(d->left_sensor, "RAM", 3) ? "RAM " :
                            !strncmp(d->left_sensor, "GPU", 3) ? "GPU " : "CPU ";
        const char *label2 = !strncmp(d->right_sensor, "NET_", 4) ? "UL " :
                            !strncmp(d->right_sensor, "VRAM", 4) ? "VM " :
                            !strncmp(d->right_sensor, "RAM", 3) ? "RAM " : "GPU ";
        if (y1 != y2) {
            design_text(c, label1, 0, left, y1 - 3, w, 6, 0);
            design_text(c, label2, 0, right, y2 - 3, w, 6, 0);
            design_value(c, d->left_sensor, "", left, y1 + 5, w, 0);
            design_value(c, d->right_sensor, "", right, y2 + 5, w, 0);
        } else {
            design_value(c, d->left_sensor, label1, left, y1, w, 0);
            design_value(c, d->right_sensor, label2, right, y2, w, 0);
        }
    }
    if (d->invert)
        for (int y = 0; y < 43; y++) for (int x = 0; x < 160; x++)
            g15r_setPixel(c, x, y, !g15r_getPixel(c, x, y));
}

static void draw_screen_design(g15canvas *c, int screen, int index) {
    if (screen == 2) design_system(c, index);
    else if (screen == 3) design_media(c, index);
    else if (screen == 4) design_games(c, index);
    else if (screen == 5) design_network(c, index);
}
#endif
