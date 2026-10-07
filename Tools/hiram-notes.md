# Hiram for the Mac Plus ROM

`hiram.c` adapts the surviving Hiram initials loop and word checksum to finish the reconstructed Mac Plus ROM. MPW SC compiles it, MPW Link builds an MPW tool, and the `mpw` emulator runs it. Hiram reads an assembled prefix, fills the remaining space with supplied initials, writes a supplied date and its trailing length, and computes the checksum. It never reads the reference ROM.

The normal build compiles Hiram and runs it from MPW Make. From the project root:

```sh
make
python3 -m unittest discover -s Tools -p 'test_hiram.py'
```

The checked-in `MPW/ROM.make` also has a `hiram` target. To compile only that tool:

```sh
make prepare
make native TARGET=hiram
```

The Makefile compiles staged MacRoman C source with `SC -w iserror`. It links `MacRuntime.o`, `StdCLib.o`, `IntEnv.o`, and `Interface.o` into an `MPST` file. The tool's executable code occupies its resource fork. `MPW` selects the MPW installation; put `mpw` and `mpw-shell` on `PATH`.

After a complete build, run Hiram separately from the project root with:

```sh
mpw Build/hiram -s 128 -i 'HB_JTC_SC_DLD_PWD_KWK_LAK_SEL_B' \
  -fd 'Wed, Nov 6, 1985' --fill-start 0x1ffd0 \
  Build/MacPlus-v3.unfinished.bin /tmp/ROMMondo
```

The input must contain exactly `0x1ffd0` bytes for this invocation. It includes the assembled code, resources, and SCSI helper. ROMBuild extracts that prefix from MPW Link's ROM resource and compresses the dispatch table before Hiram runs. Hiram replaces the first four bytes with the checksum and preserves every other input byte. The `-s` argument gives the output size in KiB; `--fill-start` gives the input size in bytes. Hiram accepts spaces in `-i` and preserves the original conversion of underscores to spaces.

## Surviving source

The [surviving Hiram source](../../supermario/base/SuperMarioProj.1994-02-09/Tools/hiram.c) remains unchanged. This historical tree is not required to build the ROM. Its SHA-256 is `19eb09aa0d4921936eea0034f5928889cf68cff1e36808a439ffcab75dbe5c9f`. The adaptation retains J. T. Coonen's attribution and Apple's copyright notice. These parts derive from that file:

| Adapted code | Original source | Change in this adaptation |
| --- | --- | --- |
| Initials loop | `readROMCode`, lines 638 through 644 | Start at the supplied prefix boundary and use a C string in place of a Mac memory handle. |
| Underscore conversion | `parseArgs`, lines 504 through 506 | Retain the conversion; omit the later string wrapper. |
| Word checksum | `computeCheckSums`, lines 1124 through 1133 | Read unsigned words in big-endian order, accumulate into `unsigned long`, and mask the sum to 32 bits. |
| Date length | Change history, May 15, 1985, line 133 | Reconstruct the recorded trailing-length format. |

The checksum covers every unsigned 16-bit word from offset four through the final word, with a 32-bit result at offset zero. Explicit byte access preserves 68000 byte order. C90 types and format strings allow MPW SC to compile the source; the explicit checksum mask also preserves 32-bit wrapping when a host compiler uses wider longs. The supplied date makes the output independent of the host clock and locale.

## Reconstruction limits

The surviving source ends in 1992. Its ROM header, resources, and date format differ from the Mac Plus format. This adaptation omits the later slice checksum fields at `0x30` and ROM size field at `0x40`, where the Mac Plus stores instructions. ROMBuild emits the Plus resource headers and labels for Asm and Link. The adaptation does not port the later resource loader, declaration data, encryption, patch loading, or slice output.

The original history records a date with a trailing length on May 15, 1985. The body of that date routine no longer survives. `putDate` reconstructs its recorded output format from the history and the Mac Plus ROM: date bytes followed by one length byte. It omits the later brackets, leading Pascal length, and copyright string.

The initials argument above records the 31 bytes visible after the SCSI helper. The complete original initials string and its position within the repeated fill remain unknown. The surviving loop fills the entire ROM before loading code. This adaptation starts the supplied string at `--fill-start` to reproduce the known fragment without inventing the missing string or its position. A longer free span would repeat that supplied fragment; that behavior does not establish what the original 1985 build would have written there.

The tests compile the C source with MPW SC, treat warnings as errors, and run the linked MPW tool through the emulator. They check preservation of code at the later header offsets, unsigned word sums, exclusion of the checksum field, inclusion of the final word, 32-bit overflow, repeated initials, date bounds, and input length checks. The complete build checks the finished image's SHA-256.
