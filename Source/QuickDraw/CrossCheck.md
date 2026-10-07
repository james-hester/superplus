# Earlier QuickDraw source comparison

All 29 reconstructed QuickDraw modules still match the Mac Plus v3 ROM after comparison with `QuickDraw Source`. The comparison covers the continuous span from `$4082C6` through `$40E5E3`, or 25,374 bytes. It preserves the existing instructions and data while restoring applicable source comments and a shared type include.

## Source changes

`GrafTypes.a` contains the earlier release's 173 declarations, with `.EQU` changed to MPW `EQU`. All 964 declarations removed from the module preambles have the same values as their counterparts in this include. Every module now uses `INCLUDE 'GrafTypes.a'`. Return and trap macros remain in their modules because their encodings must match the ROM.

The earlier header defines the private globals through `QDSpareD`, including `QDSpare3`, and derives `lastGrafGlob = -202`. `GrafInit.a` now uses its matching `QDSpareD..QDSpare3` initialization comment. The header's stale reference to `52(A5)` is corrected to `0(A5)`, consistent with both releases' `GRAFGLOBALS` equate and the ROM.

`Pictures.a` regains the earlier bitmap reader's opcode descriptions and packing-loop comments. That reader had survived in the reconstruction as code recovered from ROM. The copied descriptions of uncompressed bitmap opcodes omit the earlier source's erroneous byte-count field; only packed scanlines store that count. `Text.a` and `DrawText.a` regain headings, font-record descriptions, and applicable instruction comments. The original ASCII banners retain their spacing. `GrafInit.a` also records the storage glue's attribution from `QuickGlue.a`.

Most other routine comments already matched the earlier release. Their new provenance notes record that corroboration. Existing Apple copyright notices and applicable change history remain intact.

## Differences retained from the ROM

The comparison accounts for assembler directives, procedure names, PC-relative operands, branch widths, quick instructions, trap aliases, and return macros before assessing code differences. The earlier source does not supersede the ROM where behavior differs.

| Area | Retained difference |
| --- | --- |
| Drawing and picture calls | The Plus obtains standard procedures from the Toolbox trap table where the earlier source takes their addresses directly. |
| `DrawArc`, `DrawLine`, `DrText`, `ColorMap` | The Plus tests for negative `colrBit`; the earlier source tests for zero. |
| `RgnBlt` | The Plus also saves and restores D0–D2. |
| Text routines | The Plus retains its scaling, signed multiplication, and pen-location restoration. Older comments promising nil-font handling were not copied into routines that lack it. |
| `Bitmaps` | The Plus retains the long address addition and calls `PackBits` directly. The stale March 1989 annotation was removed from that call. |
| `BitBlt` | The ROM's embedded copyright bytes remain unchanged. |

The earlier source also contains `PutRgn`'s two-corner rectangle path and `RgnOp`'s signed buffer-size addition. These corroborate the existing reconstruction. Both the earlier `Pictures.a` and the ROM unlock the handle in `PutPicRgn`; both retain the duplicate lock in `GETHNDL`. The SuperMario history entry dated April 14, 1986 remains as source history, but this comparison does not establish the earlier release's date or resolve the ROM filename's chronology.

## Verification

Run from the project root:

```sh
make
make test
```

The complete ROM link resolves QuickDraw's imports from other modules. MPW Asm and Link produce the code, and `make` checks the finished image's SHA-256. Put `mpw` and `mpw-shell` on `PATH`.

The build writes output to `Build/` by default. Run `make BUILD=/private/tmp/quickdraw-build` to choose another directory. All 29 QuickDraw modules use the shared MPW Asm driver and the checked-in `MPW/ROM.make`. Python converts source text for MPW without parsing includes, instructions, or labels.
