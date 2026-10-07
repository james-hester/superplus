/*
	File:		Hiram.c

	Written by:	J. T. Coonen

	Copyright:	© 1985-1990, 1992 by Apple Computer, Inc., all rights reserved.
*/

/*
 * This adaptation finishes the reconstructed Mac Plus ROM.
 * The initials loop and word checksum derive from Tools/hiram.c, whose
 * original source remains unchanged. See hiram-notes.md for provenance.
 *
 * The input contains assembled code and resources through --fill-start.
 * The output adds initials, an explicit date, its trailing length byte,
 * and the checksum. Standard C file operations replace the Mac OS calls.
 * Byte access replaces casts to the host's short and long types.
 */

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define Chekov 0x0000 /* Offset to checksum in ROM */

static void fail(const char *message)
{
    fprintf(stderr, "Hiram: %s\n", message);
    exit(EXIT_FAILURE);
}

static void usage(FILE *stream)
{
    fputs("Usage: hiram -s KIB -i INITIALS -fd DATE --fill-start OFFSET INPUT OUTPUT\n",
          stream);
}

static size_t number(const char *text)
{
    char *end;
    unsigned long value;

    if (text[0] < '0' || text[0] > '9')
        fail("invalid numeric argument");
    errno = 0;
    value = strtoul(text, &end, 0);
    if (errno != 0 || *end != '\0' || value > (size_t)-1)
        fail("invalid numeric argument");
    return (size_t)value;
}

static void printable(const char *text)
{
    const unsigned char *p = (const unsigned char *)text;

    for (; *p; ++p)
        if (*p < 0x20 || *p > 0x7e)
            fail("initials and date must contain printable ASCII");
}

static void readROMCode(const char *path, unsigned char *ROMImage, size_t CodeSize)
{
    FILE *input = fopen(path, "rb");
    size_t count;
    int extra;

    if (input == NULL)
        fail("cannot open input image");
    count = fread(ROMImage, 1, CodeSize, input);
    extra = fgetc(input);
    if (ferror(input))
        fail("cannot read input image");
    if (fclose(input) != 0)
        fail("cannot close input image");
    if (count != CodeSize || extra != EOF)
        fail("input length must equal --fill-start");
}

static void fillInitials(unsigned char *ROMImage, size_t ROMLEN,
                         size_t fillStart, const char *initials)
{
    unsigned char *codePtr = ROMImage + fillStart;
    const char *namePtr = initials;
    size_t i;

    /* Tools/hiram.c, readROMCode: restart the initials at the string end. */
    for (i = fillStart; i < ROMLEN; i++) {
        *codePtr++ = (unsigned char)*namePtr++;
        if (*namePtr == 0)
            namePtr = initials;
    }
}

static void putDate(unsigned char *ROMImage, size_t ROMLEN, const char *date)
{
    size_t length = strlen(date);

    /* Reconstruct the trailing length recorded in the May 15, 1985 history. */
    memcpy(ROMImage + ROMLEN - length - 1, date, length);
    ROMImage[ROMLEN - 1] = (unsigned char)length;
}

/*
** Accumulate 16-bit words into 32-bit sum, stuff it in first long.
** Have ROMLEN-4 bytes to be split into words for the sum.
*/
static unsigned long computeCheckSums(unsigned char *ROMImage, size_t ROMLEN)
{
    const unsigned char *wp = ROMImage + 4;
    const size_t top = (ROMLEN - 4) / 2;
    unsigned long cs = 0;
    size_t i;

    /** calc main during loop through ROMImage **/
    for (i = 0; i < top; i++) {
        cs = (cs + (((unsigned long)wp[0] << 8) | wp[1])) & 0xffffffffUL;
        wp += 2;
    }

    /** store the complete checksum in the ROM Image **/
    ROMImage[Chekov] = (unsigned char)(cs >> 24);
    ROMImage[Chekov + 1] = (unsigned char)(cs >> 16);
    ROMImage[Chekov + 2] = (unsigned char)(cs >> 8);
    ROMImage[Chekov + 3] = (unsigned char)cs;
    return cs;
}

static void writeROMOutputs(const char *path, const unsigned char *ROMImage,
                            size_t ROMLEN)
{
    FILE *output = fopen(path, "wb");
    size_t count;
    int closeResult;

    if (output == NULL)
        fail("cannot open output image");
    count = fwrite(ROMImage, 1, ROMLEN, output);
    closeResult = fclose(output);
    if (count != ROMLEN || closeResult != 0) {
        remove(path);
        fail("cannot write output image");
    }
}

int main(int argc, char **argv)
{
    size_t ROMLEN = 0, fillStart = 0, dateLength;
    const char *initialsArg = NULL, *date = NULL;
    const char *input, *output;
    char *initials, *s;
    unsigned char *ROMImage;
    unsigned long checksum;
    int arg = 1, haveFillStart = 0;

    if (argc == 2 && strcmp(argv[1], "--help") == 0) {
        usage(stdout);
        return EXIT_SUCCESS;
    }
    while (arg < argc && argv[arg][0] == '-') {
        const char *option = argv[arg++];
        const char *value;
        if (arg == argc) {
            usage(stderr);
            fail("missing option value");
        }
        value = argv[arg++];
        if (strcmp(option, "-s") == 0 && ROMLEN == 0) {
            size_t kib = number(value);
            if (kib == 0 || kib > (size_t)-1 / 1024)
                fail("ROM size must be a positive number of KiB");
            ROMLEN = kib * 1024;
        } else if (strcmp(option, "-i") == 0 && initialsArg == NULL) {
            initialsArg = value;
        } else if (strcmp(option, "-fd") == 0 && date == NULL) {
            date = value;
        } else if (strcmp(option, "--fill-start") == 0 && !haveFillStart) {
            fillStart = number(value);
            haveFillStart = 1;
        } else {
            usage(stderr);
            fail("unknown or repeated option");
        }
    }
    if (argc - arg != 2 || ROMLEN == 0 || !haveFillStart ||
        initialsArg == NULL || date == NULL) {
        usage(stderr);
        fail("size, initials, date, fill start, input, and output are required");
    }
    input = argv[arg];
    output = argv[arg + 1];
    if (strcmp(input, output) == 0)
        fail("input and output paths must differ");
    printable(initialsArg);
    printable(date);
    if (initialsArg[0] == '\0')
        fail("initials must not be empty");
    dateLength = strlen(date);
    if (dateLength > 255)
        fail("date exceeds the trailing length byte");
    if (fillStart < 4 || fillStart > ROMLEN - dateLength - 1)
        fail("date overlaps the input image or fill start is outside the ROM");

    ROMImage = malloc(ROMLEN);
    initials = malloc(strlen(initialsArg) + 1);
    if (ROMImage == NULL || initials == NULL)
        fail("cannot allocate image memory");
    strcpy(initials, initialsArg);
    /* Preserve the underscore conversion in Tools/hiram.c, parseArgs. */
    for (s = initials; *s != '\0'; s++)
        if (*s == '_')
            *s = ' ';

    readROMCode(input, ROMImage, fillStart);
    fillInitials(ROMImage, ROMLEN, fillStart, initials);
    putDate(ROMImage, ROMLEN, date);
    checksum = computeCheckSums(ROMImage, ROMLEN);
    writeROMOutputs(output, ROMImage, ROMLEN);
    printf("Hiram: wrote %lu bytes, checksum 0x%08lx\n", (unsigned long)ROMLEN, checksum);
    free(initials);
    free(ROMImage);
    return EXIT_SUCCESS;
}
