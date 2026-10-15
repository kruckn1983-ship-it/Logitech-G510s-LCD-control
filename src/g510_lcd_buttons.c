#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <linux/input.h>
#include <sys/stat.h>

#define NUM_SCREENS 2

/* User-specific by nature -- built at runtime from $HOME rather than
   baked in at compile time, so this file doesn't hardcode a username. */
static const char *button_log_path(void) {
    static char path[256];
    const char *home = getenv("HOME");
    snprintf(path, sizeof(path), "%s/.local/share/g510lcd-buttons.log", home ? home : "/tmp");
    return path;
}

static const char *screen_state_path(void) {
    static char path[256];
    const char *runtime = getenv("XDG_RUNTIME_DIR");
    snprintf(path, sizeof(path), "%s/g510lcd_screen", runtime ? runtime : "/tmp");
    return path;
}

static const char *persistent_screen_state_path(void) {
    static char path[256];
    const char *home = getenv("HOME");
    snprintf(path, sizeof(path), "%s/.local/share/g510-lcd/active_screen",
             home ? home : "/tmp");
    return path;
}

static void mkdir_p(const char *path) {
    char tmp[256];
    snprintf(tmp, sizeof(tmp), "%s", path);
    for (char *p = tmp + 1; *p; p++) {
        if (*p == '/') {
            *p = '\0';
            mkdir(tmp, 0755);
            *p = '/';
        }
    }
    mkdir(tmp, 0755);
}

static const char *key_name(int code) {
    switch (code) {
        case 696: return "L1";
        case 697: return "L2";
        case 698: return "L3";
        case 699: return "L4";
        case 700: return "L5";
        default: return "?";
    }
}

static int read_screen(void) {
    const char *paths[] = {
        screen_state_path(),
        persistent_screen_state_path()
    };
    for (size_t i = 0; i < sizeof(paths) / sizeof(paths[0]); i++) {
        FILE *f = fopen(paths[i], "r");
        if (!f) continue;
        int s = -1;
        char extra;
        int valid = fscanf(f, "%d %c", &s, &extra) == 1 && s >= 0 && s <= 5;
        fclose(f);
        if (valid) return s;
    }
    return 0;
}

static void write_screen(int s) {
    if (s < 0 || s > 5) {
        fprintf(stderr, "g510-lcd-buttons: refusing invalid screen number %d\n", s);
        return;
    }

    const char *paths[] = {
        screen_state_path(),
        persistent_screen_state_path()
    };
    const char *home = getenv("HOME");
    char data_dir[256];
    snprintf(data_dir, sizeof(data_dir), "%s/.local/share/g510-lcd",
             home ? home : "/tmp");
    mkdir_p(data_dir);

    for (size_t i = 0; i < sizeof(paths) / sizeof(paths[0]); i++) {
        FILE *f = fopen(paths[i], "w");
        if (!f) {
            perror(paths[i]);
            continue;
        }
        int write_failed = fprintf(f, "%d\n", s) < 0;
        if (fclose(f) != 0) write_failed = 1;
        if (write_failed) {
            perror(paths[i]);
        }
    }
}

static void log_button(const char *name) {
    FILE *f = fopen(button_log_path(), "a");
    if (!f) return;
    time_t now = time(NULL);
    char buf[32];
    strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", localtime(&now));
    fprintf(f, "[%s] %s pressed\n", buf, name);
    fclose(f);
}

#define DEBOUNCE_MS 400

static long ms_since(struct timespec *last) {
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (now.tv_sec - last->tv_sec) * 1000 + (now.tv_nsec - last->tv_nsec) / 1000000;
}

int main(void) {
    FILE *f = fopen("/dev/g510-keys", "rb");
    if (!f) { perror("open /dev/g510-keys"); return 1; }

    /* These switches bounce (confirmed: single physical presses were
       logging 2-4 times). Track the last accepted press time per key
       (indices 696-700) and ignore repeats within DEBOUNCE_MS. */
    struct timespec last_press[701] = {0};

    struct input_event ev;
    while (fread(&ev, sizeof(ev), 1, f) == 1) {
        if (ev.type != EV_KEY || ev.value != 1) continue; /* only key-down */
        if (ev.code < 696 || ev.code > 700) continue;

        if (last_press[ev.code].tv_sec != 0 && ms_since(&last_press[ev.code]) < DEBOUNCE_MS) {
            continue; /* bounce, ignore */
        }
        clock_gettime(CLOCK_MONOTONIC, &last_press[ev.code]);

        if (ev.code == 696) { /* L1: cycle stats/clock, or return to stats from a test screen */
            int cur = read_screen();
            write_screen(cur >= 2 ? 0 : (cur + 1) % NUM_SCREENS);
        } else { /* L2-L5: show a test screen confirming the press, and log it */
            write_screen(ev.code - 695); /* 697->2, 698->3, 699->4, 700->5 */
            log_button(key_name(ev.code));
        }
    }
    fclose(f);
    return 0;
}
