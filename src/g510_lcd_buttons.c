#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <linux/input.h>
#include <unistd.h>
#include <sys/wait.h>
#include <errno.h>

/* User-specific by nature -- built at runtime from $HOME rather than
   baked in at compile time, so this file doesn't hardcode a username. */
static const char *button_log_path(void) {
    static char path[256];
    const char *home = getenv("HOME");
    snprintf(path, sizeof(path), "%s/.local/share/g510lcd-buttons.log", home ? home : "/tmp");
    return path;
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

static void handle_key(const char *key) {
    char helper[4096];
    ssize_t length = readlink("/proc/self/exe", helper, sizeof(helper) - 1);
    if (length < 0) { perror("readlink LCD key helper"); return; }
    helper[length] = 0;
    char *slash = strrchr(helper, '/');
    if (!slash || (size_t)(slash - helper) + sizeof("/g510_screen_keys.py") > sizeof(helper)) {
        fprintf(stderr, "g510-lcd-buttons: invalid helper path\n");
        return;
    }
    strcpy(slash, "/g510_screen_keys.py");
    pid_t child = fork();
    if (child < 0) { perror("fork LCD action"); return; }
    if (child == 0) {
        execlp("python3", "python3", helper, key, (char *)NULL);
        perror("exec LCD action");
        _exit(127);
    }
    int status;
    pid_t result;
    do { result = waitpid(child, &status, 0); } while (result < 0 && errno == EINTR);
    if (result < 0) perror("wait LCD action");
    else if (!WIFEXITED(status) || WEXITSTATUS(status) != 0)
        fprintf(stderr, "g510-lcd-buttons: action for %s failed (status %d)\n", key, status);
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
    /* evdev is a live stream: buffered fread can wait for more events
       after receiving a complete key press. */
    if (setvbuf(f, NULL, _IONBF, 0) != 0) {
        fprintf(stderr, "g510-lcd-buttons: cannot disable input buffering\n");
        fclose(f);
        return 1;
    }

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

        log_button(key_name(ev.code));
        handle_key(key_name(ev.code));
    }
    int failed = ferror(f);
    if (failed) perror("read /dev/g510-keys");
    fclose(f);
    return failed ? 1 : 0;
}
