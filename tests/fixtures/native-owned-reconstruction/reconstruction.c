/* Independent source-owned reconstruction hypothesis; NOT decompiler output. */
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
static long reconstructed(long input) {
    long multiplier = input < -7 ? 3L : (input > 9 ? 7L : input);
    long addition = input < -7 ? -11L : (input > 9 ? -2L : 5L);
    return multiplier * input + addition;
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
