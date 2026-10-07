/* Pack ROM resources and compress the linked dispatch table. */

#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <Files.h>
#include <MacMemory.h>
#include <Resources.h>

#define ENTRY_COUNT 768
#define TABLE_BYTES (ENTRY_COUNT * 4UL)
#define MAX_ENCODED_BYTES (ENTRY_COUNT * 5UL + 4)
#define LAYOUT_BYTES 28UL
#define LAYOUT_MAGIC 0x52424c44UL

static FILE *resourceOutput = NULL;
static const char *resourceOutputPath = NULL;

static void fail(const char *message)
{
    if (resourceOutput != NULL)
        fclose(resourceOutput);
    if (resourceOutputPath != NULL)
        remove(resourceOutputPath);
    fprintf(stderr, "ROMBuild: %s\n", message);
    exit(EXIT_FAILURE);
}

static void usage(FILE *stream)
{
    fputs("Usage: rombuild --resources LAYOUT INPUT OUTPUT\n", stream);
    fputs("   or: rombuild --dispatch-offset OFFSET --rom-size BYTES INPUT OUTPUT\n", stream);
    fputs("   or: rombuild --resolve-layout SIZEFILE --status-file STATUSFILE --rom-size BYTES INPUT OUTPUT\n", stream);
}

static unsigned long number(const char *text)
{
    char *end;
    unsigned long value;

    if (text[0] < '0' || text[0] > '9')
        fail("invalid numeric argument");
    errno = 0;
    value = strtoul(text, &end, 0);
    if (errno != 0 || *end != '\0')
        fail("invalid numeric argument");
    return value;
}

#define RESOURCE_LABEL_BYTES 64
#define RESOURCE_LINE_BYTES 1024

typedef struct {
    ResType type;
    short id;
    short attributes;
    char label[RESOURCE_LABEL_BYTES];
    unsigned char name[256];
} ResourceEntry;

static int hexDigit(int value)
{
    if (value >= '0' && value <= '9')
        return value - '0';
    if (value >= 'A' && value <= 'F')
        return value - 'A' + 10;
    if (value >= 'a' && value <= 'f')
        return value - 'a' + 10;
    fail("invalid hexadecimal resource layout field");
    return 0;
}

static unsigned long decimal(const char *text, unsigned long maximum)
{
    unsigned long value = 0;
    const unsigned char *p = (const unsigned char *)text;

    if (*p == 0)
        fail("empty decimal resource layout field");
    while (*p != 0) {
        unsigned int digit;
        if (*p < '0' || *p > '9')
            fail("invalid decimal resource layout field");
        digit = *p++ - '0';
        if (value > maximum / 10 ||
            (value == maximum / 10 && digit > maximum % 10))
            fail("resource layout value exceeds its field bounds");
        value = value * 10 + digit;
    }
    return value;
}

static void identifier(const char *name)
{
    size_t length = strlen(name), i;

    if (length == 0 || length >= RESOURCE_LABEL_BYTES ||
        !isalpha((unsigned char)name[0]))
        fail("invalid resource label");
    for (i = 0; i < length; i++)
        if ((unsigned char)name[i] > 127 ||
            (!isalnum((unsigned char)name[i]) && name[i] != '_'))
            fail("invalid resource label");
}

static int sameSymbol(const char *a, const char *b)
{
    while (*a != 0 && *b != 0) {
        if (tolower((unsigned char)*a++) != tolower((unsigned char)*b++))
            return 0;
    }
    return *a == *b;
}

static int layoutLine(FILE *file, char *line, char **fields, int count)
{
    char *p;
    int index = 0, byte, gotLine = 0;
    size_t length = 0;

    while ((byte = fgetc(file)) != EOF) {
        gotLine = 1;
        if (byte == 13 || byte == 10) {
            if (byte == 13) {
                byte = fgetc(file);
                if (byte != 10 && byte != EOF)
                    ungetc(byte, file);
            }
            break;
        }
        if (byte != 9 && (byte < 32 || byte > 126))
            fail("resource layout must contain ASCII text");
        if (length == RESOURCE_LINE_BYTES - 1)
            fail("resource layout line is too long");
        line[length++] = (char)byte;
    }
    if (ferror(file))
        fail("cannot read resource layout");
    if (byte == EOF && !gotLine)
        return 0;
    line[length] = 0;
    p = line;
    while (*p != 0) {
        while (*p == ' ' || *p == '\t')
            p++;
        if (*p == 0)
            break;
        if (index == count)
            fail("too many resource layout fields");
        fields[index++] = p;
        while (*p != 0 && *p != ' ' && *p != '\t') {
            if ((unsigned char)*p < 33 || (unsigned char)*p > 126)
                fail("resource layout must contain ASCII text");
            p++;
        }
        if (*p != 0)
            *p++ = 0;
    }
    if (index != count)
        fail("missing resource layout fields");
    return 1;
}

static void checkResourceSymbols(const ResourceEntry *entries, unsigned int index,
                                 const char *module)
{
    static const char *suffixes[] = {"", "Block", "End"};
    char current[RESOURCE_LABEL_BYTES + 6], previous[RESOURCE_LABEL_BYTES + 6];
    unsigned int j, a, b;

    for (a = 0; a < 3; a++) {
        sprintf(current, "%s%s", entries[index].label, suffixes[a]);
        if (sameSymbol(current, module))
            fail("resource label duplicates the module label");
        for (j = 0; j < index; j++) {
            if (entries[index].type == entries[j].type && entries[index].id == entries[j].id)
                fail("duplicate resource layout entry");
            for (b = 0; b < 3; b++) {
                sprintf(previous, "%s%s", entries[j].label, suffixes[b]);
                if (sameSymbol(current, previous))
                    fail("duplicate generated resource label");
            }
        }
    }
}

static short openResources(const char *path)
{
    unsigned char name[256];
    size_t length = strlen(path);
    short file;

    if (length > 255)
        fail("resource input path exceeds 255 bytes");
    name[0] = (unsigned char)length;
    memcpy(name + 1, path, length);
    file = OpenResFile(name);
    if (file == -1 || ResError() != 0)
        fail("cannot open input resource file");
    return file;
}

static Handle checkedResource(const ResourceEntry *entry)
{
    Handle resource;
    short id, attributes;
    ResType type;
    unsigned char name[256];
    Size size;

    resource = Get1Resource(entry->type, entry->id);
    if (resource == NULL || ResError() != 0)
        fail("resource layout names a missing resource");
    GetResInfo(resource, &id, &type, name);
    if (ResError() != 0 || id != entry->id || type != entry->type ||
        memcmp(name, entry->name, (size_t)entry->name[0] + 1) != 0)
        fail("resource name or identity differs from layout");
    attributes = GetResAttrs(resource);
    if (ResError() != 0 || attributes != entry->attributes)
        fail("resource attributes differ from layout");
    size = GetHandleSize(resource);
    if (size < 0 || (unsigned long)size > 0xffffffUL - 8)
        fail("resource exceeds the ROM block size field");
    return resource;
}

static void packResources(const char *layoutPath, const char *inputPath, const char *outputPath)
{
    FILE *layout;
    char line[RESOURCE_LINE_BYTES], *fields[5], module[RESOURCE_LABEL_BYTES];
    ResourceEntry *entries;
    unsigned long flags, master, count, total = 0;
    unsigned int i, j;
    short file, typeCount;
    unsigned char outputName[256];
    FInfo outputInfo;
    int failed;

    if (strcmp(layoutPath, inputPath) == 0 || strcmp(layoutPath, outputPath) == 0 ||
        strcmp(inputPath, outputPath) == 0)
        fail("resource layout, input, and output paths must differ");
    if (strlen(outputPath) > 255)
        fail("resource output path exceeds 255 bytes");
    resourceOutputPath = outputPath;
    layout = fopen(layoutPath, "rb");
    if (layout == NULL)
        fail("cannot open resource layout");
    if (!layoutLine(layout, line, fields, 4))
        fail("resource layout is empty");
    identifier(fields[0]);
    strcpy(module, fields[0]);
    flags = decimal(fields[1], 255);
    master = decimal(fields[2], 0xffffffffUL);
    count = decimal(fields[3], 32767);
    if (count == 0 || (master & 3) != 0 ||
        (count - 1) > (0xffffffffUL - master) / 4)
        fail("invalid resource count or master pointer bounds");
    entries = calloc((size_t)count, sizeof(ResourceEntry));
    if (entries == NULL)
        fail("cannot allocate resource layout");
    for (i = 0; i < count; i++) {
        unsigned long type = 0, id;
        const char *idText;
        size_t nameLength;

        if (!layoutLine(layout, line, fields, 5))
            fail("resource layout omits declared entries");
        if (strlen(fields[0]) != 8)
            fail("resource type must contain eight hexadecimal digits");
        for (j = 0; j < 8; j++)
            type = (type << 4) | hexDigit(fields[0][j]);
        entries[i].type = (ResType)type;
        idText = fields[1];
        if (*idText == '-') {
            id = decimal(idText + 1, 32768);
            entries[i].id = (short)(-(long)id);
        } else {
            id = decimal(idText, 32767);
            entries[i].id = (short)id;
        }
        entries[i].attributes = (short)decimal(fields[2], 255);
        identifier(fields[3]);
        strcpy(entries[i].label, fields[3]);
        checkResourceSymbols(entries, i, module);
        if (strcmp(fields[4], "-") != 0) {
            nameLength = strlen(fields[4]);
            if ((nameLength & 1) != 0 || nameLength > 510)
                fail("invalid resource name length");
            entries[i].name[0] = (unsigned char)(nameLength / 2);
            for (j = 0; j < nameLength / 2; j++)
                entries[i].name[j + 1] = (unsigned char)
                    ((hexDigit(fields[4][j * 2]) << 4) | hexDigit(fields[4][j * 2 + 1]));
        }
    }
    if (layoutLine(layout, line, fields, 5))
        fail("resource layout contains undeclared entries");
    if (fclose(layout) != 0)
        fail("cannot close resource layout");
    file = openResources(inputPath);
    typeCount = Count1Types();
    if (ResError() != 0 || typeCount < 0)
        fail("cannot count resource types");
    for (i = 1; i <= (unsigned int)typeCount; i++) {
        ResType type;
        short resources;
        Get1IndType(&type, (short)i);
        if (ResError() != 0)
            fail("cannot read resource type");
        resources = Count1Resources(type);
        if (ResError() != 0 || resources < 0)
            fail("cannot count resources");
        total += resources;
    }
    if (total != count)
        fail("resource count differs from layout");
    for (i = 0; i < count; i++)
        ReleaseResource(checkedResource(&entries[i]));
    resourceOutput = fopen(outputPath, "wb");
    if (resourceOutput == NULL)
        fail("cannot open resource assembly output");
    fprintf(resourceOutput, "%s PROC EXPORT\r", module);
    for (i = 0; i < count; i++) {
        Handle resource = checkedResource(&entries[i]);
        unsigned long size = (unsigned long)GetHandleSize(resource), offset;
        const char *label = entries[i].label;

        fprintf(resourceOutput, "\tEXPORT %s,%sBlock,%sEnd\r%sBlock EQU *\r",
                label, label, label, label);
        fprintf(resourceOutput, "\tDC.B $%lx,$%lx,$%lx,$%lx\r",
                flags, ((size + 8) >> 16) & 255, ((size + 8) >> 8) & 255, (size + 8) & 255);
        fprintf(resourceOutput, "\tDC.B $%lx,$%lx,$%lx,$%lx\r%s EQU *\r",
                master >> 24, (master >> 16) & 255, (master >> 8) & 255, master & 255, label);
        HLock(resource);
        for (offset = 0; offset < size; offset++) {
            if (offset % 20 == 0)
                fputs("\tDC.B ", resourceOutput);
            fprintf(resourceOutput, "%u", (unsigned char)(*resource)[offset]);
            fputc(offset % 20 == 19 || offset + 1 == size ? '\r' : ',', resourceOutput);
        }
        HUnlock(resource);
        ReleaseResource(resource);
        fprintf(resourceOutput, "%sEnd EQU *\r", label);
        master += 4;
    }
    fputs("\tENDP\r\tEND\r", resourceOutput);
    failed = ferror(resourceOutput);
    failed |= fclose(resourceOutput) != 0;
    resourceOutput = NULL;
    if (failed)
        fail("cannot write resource assembly");
    outputName[0] = (unsigned char)strlen(outputPath);
    memcpy(outputName + 1, outputPath, outputName[0]);
    if (GetFInfo(outputName, 0, &outputInfo) != 0)
        fail("cannot read resource assembly file information");
    outputInfo.fdType = 'TEXT';
    outputInfo.fdCreator = 'MPS ';
    if (SetFInfo(outputName, 0, &outputInfo) != 0)
        fail("cannot mark resource assembly as text");
    CloseResFile(file);
    if (ResError() != 0)
        fail("cannot close input resource file");
    free(entries);
    resourceOutputPath = NULL;
}

static unsigned char *readCode(const char *path, size_t *length)
{
    unsigned char name[256];
    size_t nameLength = strlen(path);
    short file;
    Handle resource;
    Size size;
    unsigned char *code;

    if (nameLength > 255)
        fail("input path exceeds 255 bytes");
    name[0] = (unsigned char)nameLength;
    memcpy(name + 1, path, nameLength);
    file = OpenResFile(name);
    if (file == -1 || ResError() != 0)
        fail("cannot open input resource file");
    resource = Get1Resource('ROM ', 0);
    if (resource == NULL || ResError() != 0)
        fail("input must contain resource 'ROM ' with ID 0");
    size = GetHandleSize(resource);
    if (size <= 0)
        fail("linked ROM resource is empty");
    code = malloc((size_t)size);
    if (code == NULL)
        fail("cannot allocate code memory");
    HLock(resource);
    memcpy(code, *resource, (size_t)size);
    HUnlock(resource);
    ReleaseResource(resource);
    CloseResFile(file);
    if (ResError() != 0)
        fail("cannot close input resource file");
    *length = (size_t)size;
    return code;
}

static unsigned long readLong(const unsigned char *p)
{
    return ((unsigned long)p[0] << 24) | ((unsigned long)p[1] << 16) |
           ((unsigned long)p[2] << 8) | p[3];
}

static size_t compressDispatch(const unsigned char *table, unsigned long romSize,
                               unsigned char *output)
{
    unsigned long previous = 0;
    size_t position = 0;
    unsigned int index;

    for (index = 0; index < ENTRY_COUNT; index++) {
        unsigned long value = readLong(table + index * 4UL);
        long delta;
        unsigned long encoded;

        if (value == 0) {
            output[position++] = 0x80;
            continue;
        }
        if ((value & 1) != 0 || value >= romSize)
            fail("invalid dispatch ROM offset");
        delta = (long)value - (long)previous;
        if (delta >= 2 && delta <= 252) {
            output[position++] = (unsigned char)(0x80 | (delta / 2));
        } else if (delta != 0 && delta >= -32768L && delta <= 32766L) {
            encoded = (unsigned long)(delta / 2) & 0x7fff;
            output[position++] = (unsigned char)(encoded >> 8);
            output[position++] = (unsigned char)encoded;
        } else {
            output[position++] = 0xff;
            output[position++] = (unsigned char)(value >> 24);
            output[position++] = (unsigned char)(value >> 16);
            output[position++] = (unsigned char)(value >> 8);
            output[position++] = (unsigned char)value;
        }
        previous = value;
    }
    output[position++] = 0;
    output[position++] = 0;
    if (position & 1)
        output[position++] = 0;
    return position;
}

static void writeCode(const char *path, const unsigned char *code, size_t length,
                      size_t tableOffset, const unsigned char *table, size_t tableLength,
                      size_t reservedLength)
{
    FILE *output = fopen(path, "wb");
    size_t suffixOffset = tableOffset + reservedLength;
    size_t suffixLength = length - suffixOffset;
    int failed;

    if (output == NULL)
        fail("cannot open output image");
    failed = fwrite(code, 1, tableOffset, output) != tableOffset;
    failed |= fwrite(table, 1, tableLength, output) != tableLength;
    failed |= fwrite(code + suffixOffset, 1, suffixLength, output) != suffixLength;
    failed |= fclose(output) != 0;
    if (failed) {
        remove(path);
        fail("cannot write output image");
    }
}

static void writeSize(const char *path, unsigned long size)
{
    FILE *file = fopen(path, "w");
    int failed;

    if (file == NULL)
        fail("cannot open dispatch size file");
    failed = fprintf(file, "DispatchBytes EQU %lu\n", size) < 0;
    failed |= fclose(file) != 0;
    if (failed)
        fail("cannot write dispatch size file");
}

static void writeStatus(const char *path, int changed, unsigned long prefixSize)
{
    FILE *file = fopen(path, "w");
    int failed;

    if (file == NULL)
        fail("cannot open layout status file");
    failed = fprintf(file, "Set DispatchChanged %d\nSet ROMPrefixSize %lu\n", changed, prefixSize) < 0;
    failed |= fclose(file) != 0;
    if (failed)
        fail("cannot write layout status file");
}

static void resolveLayout(unsigned char *code, size_t length, unsigned long romSize,
                          const char *sizePath, const char *statusPath, const char *output)
{
    const unsigned char *layout;
    unsigned long tableStart, tableEnd, offsetsStart, prefixEnd;
    unsigned char encoded[MAX_ENCODED_BYTES];
    size_t encodedLength;
    int changed;

    if (length < LAYOUT_BYTES + TABLE_BYTES)
        fail("linked ROM omits layout metadata");
    layout = code + length - LAYOUT_BYTES;
    if (readLong(layout) != LAYOUT_MAGIC || readLong(layout + 4) != 1 ||
        readLong(layout + 24) != ENTRY_COUNT)
        fail("invalid linked layout metadata");
    tableStart = readLong(layout + 8);
    tableEnd = readLong(layout + 12);
    offsetsStart = readLong(layout + 16);
    prefixEnd = readLong(layout + 20);
    if (((tableStart | tableEnd | offsetsStart | prefixEnd) & 1) != 0 ||
        tableStart < 4 || tableEnd < tableStart || tableEnd > prefixEnd ||
        prefixEnd != offsetsStart || prefixEnd > romSize ||
        offsetsStart != length - LAYOUT_BYTES - TABLE_BYTES ||
        tableEnd - tableStart < ENTRY_COUNT + 2 ||
        tableEnd - tableStart > MAX_ENCODED_BYTES)
        fail("linked layout offsets do not bound the ROM prefix and dispatch data");
    encodedLength = compressDispatch(code + offsetsStart, romSize, encoded);
    changed = encodedLength != tableEnd - tableStart;
    if (changed) {
        remove(output);
        writeSize(sizePath, (unsigned long)encodedLength);
    } else {
        writeCode(output, code, (size_t)prefixEnd, (size_t)tableStart,
                  encoded, encodedLength, encodedLength);
    }
    writeStatus(statusPath, changed, prefixEnd);
    printf("ROMBuild: dispatch offset %lu, reserved %lu, encoded %lu; prefix %lu bytes%s\n",
           tableStart, tableEnd - tableStart, (unsigned long)encodedLength, prefixEnd,
           changed ? "; relink required" : "");
}

int main(int argc, char **argv)
{
    unsigned long dispatchOffset = 0, romSize = 0;
    int haveDispatch = 0, arg = 1;
    unsigned char *code;
    static unsigned char encoded[MAX_ENCODED_BYTES];
    size_t length, encodedLength, outputLength;
    const char *input, *output;
    const char *sizePath = NULL, *statusPath = NULL;

    if (argc == 5 && strcmp(argv[1], "--resources") == 0) {
        packResources(argv[2], argv[3], argv[4]);
        return EXIT_SUCCESS;
    }
    if (argc == 2 && strcmp(argv[1], "--help") == 0) {
        usage(stdout);
        return EXIT_SUCCESS;
    }
    while (arg < argc && argv[arg][0] == '-') {
        const char *option = argv[arg++];
        const char *argument;
        unsigned long value;

        if (arg == argc)
            fail("missing option value");
        argument = argv[arg++];
        if (strcmp(option, "--resolve-layout") == 0 && sizePath == NULL) {
            sizePath = argument;
            continue;
        }
        if (strcmp(option, "--status-file") == 0 && statusPath == NULL) {
            statusPath = argument;
            continue;
        }
        value = number(argument);
        if (strcmp(option, "--dispatch-offset") == 0 && !haveDispatch) {
            dispatchOffset = value;
            haveDispatch = 1;
        } else if (strcmp(option, "--rom-size") == 0 && romSize == 0) {
            if (value == 0 || value > LONG_MAX)
                fail("ROM size must fit a positive signed long");
            romSize = value;
        } else {
            usage(stderr);
            fail("unknown or repeated option");
        }
    }
    if (argc - arg != 2 || romSize == 0 ||
        (sizePath == NULL && (!haveDispatch || statusPath != NULL)) ||
        (sizePath != NULL && (haveDispatch || statusPath == NULL))) {
        usage(stderr);
        fail("dispatch offset, ROM size, input, and output are required");
    }
    input = argv[arg];
    output = argv[arg + 1];
    if (strcmp(input, output) == 0)
        fail("input and output paths must differ");
    if (sizePath != NULL && (strcmp(sizePath, input) == 0 || strcmp(sizePath, output) == 0 ||
        strcmp(statusPath, input) == 0 || strcmp(statusPath, output) == 0 ||
        strcmp(sizePath, statusPath) == 0))
        fail("layout files, input, and output paths must differ");
    code = readCode(input, &length);
    if (sizePath != NULL) {
        resolveLayout(code, length, romSize, sizePath, statusPath, output);
        free(code);
        return EXIT_SUCCESS;
    }
    if ((dispatchOffset & 1) != 0 || dispatchOffset > length ||
        length - dispatchOffset < TABLE_BYTES)
        fail("dispatch table lies outside the linked code or is unaligned");
    encodedLength = compressDispatch(code + dispatchOffset, romSize, encoded);
    if (length - TABLE_BYTES > romSize ||
        encodedLength > romSize - (length - TABLE_BYTES))
        fail("compressed code exceeds ROM size");
    outputLength = length - TABLE_BYTES + encodedLength;
    writeCode(output, code, length, (size_t)dispatchOffset, encoded, encodedLength, TABLE_BYTES);
    printf("ROMBuild: wrote %lu bytes; dispatch table %lu -> %lu bytes\n",
           (unsigned long)outputLength, TABLE_BYTES, (unsigned long)encodedLength);
    free(code);
    return EXIT_SUCCESS;
}
