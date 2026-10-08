/* Deliberately wrong candidate. Boundary x=9 must be detected. */
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
static long reconstructed(long x) {
    if (x < -7) return 3L*x - 11L;
    if (x < 9) return x*x + 5L;  /* BUG: should include x=9 */
    return 7L*x - 2L;
}
int main(int argc, char **argv) {
    if (argc != 2) return 64;
    errno=0;
    char *end=0;
    long x=strtol(argv[1],&end,10);
    if (errno || !end || *end || x < -1000 || x > 1000) return 65;
    printf("%ld\n", reconstructed(x));
    return 0;
}
