/* Hazewave original, source-owned synthetic native behavior oracle. */
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
static long transfer(long x) {
    if (x < -7) { return 3L * x - 11L; }
    if (x <= 9) { return x * x + 5L; }
    return 7L * x - 2L;
}
int main(int argc, char **argv) {
    if (argc != 2) return 64;
    errno=0;
    char *end=0;
    long x=strtol(argv[1],&end,10);
    if (errno || !end || *end || x < -1000 || x > 1000) return 65;
    printf("%ld\n", transfer(x));
    return 0;
}
