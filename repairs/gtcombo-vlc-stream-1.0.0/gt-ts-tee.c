/* Nonblocking mirror of the existing native audio DVR reader.
 * Linux AArch64 libc ABI declarations keep this independent of a host sysroot.
 * No CA calls, device writes, routing operations, or payload modification. */
typedef __SIZE_TYPE__ size_t;
typedef long ssize_t;
extern void *dlsym(void *, const char *);
extern int *__errno_location(void);
extern int socket(int, int, int);
extern int setsockopt(int, int, int, const void *, unsigned int);
extern ssize_t sendto(int, const void *, size_t, int, const void *, unsigned int);
extern ssize_t readlink(const char *, char *, size_t);
extern int snprintf(char *, size_t, const char *, ...);
extern int strcmp(const char *, const char *);
extern void *memcpy(void *, const void *, size_t);
struct unix_address { unsigned short family; char path[108]; };
static ssize_t (*next_read)(int, void *, size_t);
static int tee_fd = -1;
static struct unix_address destination = {1, "/run/gt-native-ts.sock"};
__attribute__((constructor)) static void setup(void)
{
    next_read = dlsym((void *)-1L, "read");
    tee_fd = socket(1, 2 | 04000 | 02000000, 0);
    if (tee_fd >= 0) {
        int size = 512 * 1024;
        setsockopt(tee_fd, 1, 7, &size, sizeof(size));
    }
}
ssize_t read(int fd, void *buffer, size_t size)
{
    if (!next_read) { *__errno_location() = 38; return -1; }
    ssize_t n = next_read(fd, buffer, size);
    int saved_errno = *__errno_location();
    if (n > 0 && n <= 188 * 1024 && tee_fd >= 0) {
        char link[64], target[128];
        snprintf(link, sizeof(link), "/proc/self/fd/%d", fd);
        ssize_t length = readlink(link, target, sizeof(target) - 1);
        if (length >= 0) {
            target[length] = 0;
            int index = !strcmp(target, "/dev/dvb/adapter0/dvr0") ? 0 :
                        !strcmp(target, "/dev/dvb/adapter0/dvr1") ? 1 : -1;
            if (index >= 0) {
                unsigned char message[188 * 1024 + 8];
                memcpy(message, "GTTS\0\0\0", 7);
                message[7] = index;
                memcpy(message + 8, buffer, (size_t)n);
                (void)sendto(tee_fd, message, (size_t)n + 8, 0x40 | 0x4000,
                             &destination, sizeof(destination));
            }
        }
    }
    *__errno_location() = saved_errno;
    return n;
}
