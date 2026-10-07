# Mac Plus ROM reconstruction

These reconstructed sources build the complete Mac Plus v3 ROM: all 131,072 bytes match the reference image. The 120 assembly and resource modules cover `$400000` through `$41FFCF`. Hiram writes the final 48 bytes and the checksum. The rebuilt image has checksum `4D1F8172` and SHA-256 `dd908e2b65772a6b1f0c859c24e9a0d3dcde17b1c6a24f4abd8955846d7895e7`.

Reconstruction files stay under this directory. `Source/` preserves original instructions, comments, attribution, and history where they apply. Assembler reconstruction notes begin with `*R ` in column one and identify restored code, including bodies absent from the surviving sources. Notes beside instructions occupy separate preceding lines; historical comments retain semicolons. The original copyright dates remain intact. `Evidence/` records source hashes, ROM addresses, changes, and the reasons for each change.

In assembler sources, `;]` marks added instructions, declarations, labels, or comments whose content is absent from SuperMario. Changes in spacing, case, comment placement, or equivalent assembler notation do not require a marker. Code and comments are compared separately across the release selected by `SUPER_MARIO_ROOT`, including code preserved in comments. Historical inline comments retain their text and placement, even when `;]` marks the instruction as added. Blank lines and `*R` notes remain unmarked.

## Verified sources

| Source | ROM addresses, inclusive | Bytes | Contents |
| --- | --- | ---: | --- |
| `Source/OS/StartMgr/StartInit.a` | `$400000–$400985` | 2,438 | ROM header, hardware setup, trap dispatch initialization, and startup services |
| `Source/OS/StartMgr/StartBoot.a` | `$400986–$400D75` | 1,008 | Boot files, debugger loading, INIT resources, Launch, and file-system and event initialization |
| `Source/OS/StartMgr/StartupTests.a` | `$400D76–$401035` | 704 | ROM and RAM tests, compressed icons, and display helpers |
| `Source/OS/StartMgr/StartErr.a` | `$401036–$4011AB` | 374 | System errors and register capture |
| `Source/OS/StartMgr/StartAlert.a` | `$4011AC–$4017DF` | 1,588 | System alert drawing, buttons, and messages |
| `Source/OS/StartMgr/ROMDebugger.a` | `$4017E0–$4019C9` | 490 | Serial debugger commands and memory access |
| `Source/OS/Queue.a` | `$4019CA–$401A41` | 120 | Enqueue, Dequeue, InitQueue |
| `Source/OS/EarlyInterrupts.a` | `$401A42–$401B11` | 208 | Level-one interrupt dispatch and queue setup |
| `Source/OS/VBLInterrupt.a` | `$401B12–$401BD7` | 198 | VBL interrupt, input service, and task dispatch |
| `Source/OS/MouseInterrupt.a` | `$401BD8–$401C29` | 82 | Mouse quadrature interrupt handling |
| `Source/OS/VerticalRetraceMgr.a` | `$401C2A–$401C89` | 96 | VBL task installation and removal |
| `Source/OS/CursorCore.a` | `$401C8A–$401F49` | 704 | Cursor drawing, hiding, shielding, and initialization |
| `Source/OS/TrapDispatcher.a` | `$401F4A–$40202F` | 230 | OS and Toolbox dispatch and trap-address access |
| `Source/OS/DeviceMgr.a` | `$402030–$402567` | 1,336 | Device dispatch, driver lifecycle, and I/O completion |
| `Source/OS/Keyboard.a` | `$402568–$4026EB` | 388 | Keyboard initialization, interrupts, and repeat service |
| `Source/OS/OSEventMgr.a` | `$4026EC–$402851` | 358 | Posting, retrieving, and flushing events |
| `Source/OS/HFS/TFS.a` | `$402852–$402C4F` | 1,022 | File-system dispatch, queues, and disk-switch recovery |
| `Source/OS/HFS/TFSCOMMON.a` | `$402C50–$402DE5` | 406 | Allocation rounding and volume metadata helpers |
| `Source/OS/HFS/TFSVOL.a` | `$402DE6–$403413` | 1,582 | Volume mounting, consistency checks, and cleanup |
| `Source/OS/HFS/TFSVOLServices.a` | `$403414–$403DA9` | 2,454 | Volume removal, names, and working directories |
| `Source/OS/HFS/MFSVOL.a` | `$403DAA–$403FF1` | 584 | MFS allocation maps and volume mounting |
| `Source/OS/HFS/TFSDIR1.a` | `$403FF2–$404293` | 674 | File control blocks, directory search, and file metadata |
| `Source/OS/HFS/MFSDIR1.a` | `$404294–$40439F` | 268 | MFS file metadata and directory lookup |
| `Source/OS/HFS/TFSDIR2.a` | `$4043A0–$40472B` | 908 | HFS catalog creation and directory updates |
| `Source/OS/HFS/MFSDIR2.a` | `$40472C–$404851` | 294 | MFS directory creation and lookup |
| `Source/OS/HFS/TFSDIR3.a` | `$404852–$404D65` | 1,300 | HFS deletion, renaming, and directory checks |
| `Source/OS/HFS/MFSDIR3.a` | `$404D66–$404EB7` | 338 | MFS deletion, renaming, and directory checks |
| `Source/OS/HFS/TFSRFN1.a` | `$404EB8–$4050FB` | 580 | File positioning and read/write transfer helpers |
| `Source/OS/HFS/MFSRFN1.a` | `$4050FC–$405143` | 72 | MFS first-block lookup |
| `Source/OS/HFS/TFSRFN2.a` | `$405144–$40557D` | 1,082 | File closing, end-of-file changes, and control blocks |
| `Source/OS/HFS/MFSRFN2.a` | `$40557E–$4055BD` | 64 | MFS end-of-file and closing helpers |
| `Source/OS/HFS/TFSRFN3.a` | `$4055BE–$4055DF` | 34 | HFS allocation entry points |
| `Source/OS/HFS/MFSRFN3.a` | `$4055E0–$4057D5` | 502 | MFS block allocation and extent mapping |
| `Source/OS/HFS/VSM.a` | `$4057D6–$405AA7` | 722 | HFS allocation bitmap and free-space management |
| `Source/OS/HFS/FXM.a` | `$405AA8–$406043` | 1,436 | HFS file extents, extension, and truncation |
| `Source/OS/HFS/CMSVCS.a` | `$406044–$4065D7` | 1,428 | HFS catalog record services |
| `Source/OS/HFS/CMMAINT.a` | `$4065D8–$4066DB` | 260 | HFS catalog keys, paths, and name updates |
| `Source/OS/HFS/BTSVCS.a` | `$4066DC–$406E37` | 1,884 | B-tree search, node access, and traversal |
| `Source/OS/HFS/BTALLOC.a` | `$406E38–$40706B` | 564 | B-tree node allocation and map updates |
| `Source/OS/HFS/BTMAINT1.a` | `$40706C–$40729F` | 564 | B-tree insertion, replacement, and deletion |
| `Source/OS/HFS/BTMAINT2.a` | `$4072A0–$407699` | 1,018 | B-tree node splitting and index maintenance |
| `Source/OS/HFS/CACHE.a` | `$40769A–$407BAD` | 1,300 | File-system cache buffers and lookup |
| `Source/OS/HFS/CACHEIO.a` | `$407BAE–$407D3F` | 402 | Cache disk reads, writes, and completion |
| `Source/OS/SCSIBoot.a` | `$407D40–$407E57` | 280 | SCSI device driver discovery and loading |
| `Source/OS/DispTable.a` | `$407E58–$4082C5` | 1,134 | Compressed Toolbox and OS trap entries |
| `Source/QuickDraw/` (29 modules) | `$4082C6–$40E5E3` | 25,374 | Cursor interface through picture playback and mapping |
| `Source/Toolbox/FontMgrInit.a` | `$40E5E4–$40E6CD` | 234 | Font initialization and dispatch entry |
| `Source/Toolbox/FontMgrCore.a` | `$40E6CE–$40F0BF` | 2,546 | Font selection, style, scaling, and width caches |
| `Source/Toolbox/FontMgr.a` | `$40F0C0–$40F455` | 918 | Font names, widths, metrics, and character tables |
| `Source/Toolbox/SegmentLoader.a` | `$40F456–$40F78F` | 826 | Segment loading, Launch, ExitToShell, and driver cleanup |
| `Source/OS/SysUtilCalls.a` | `$40F790–$40F7DB` | 76 | Parameter RAM and date/time entry points |
| `Source/OS/SysUtil.a` | `$40F7DC–$40FC89` | 1,198 | Delay, string routines, and character tables |
| `Source/OS/Clock.a` | `$40FC8A–$40FE75` | 492 | Clock and parameter RAM access |
| `Source/OS/MemoryMgr/MemoryMgr.a` | `$40FE76–$41045D` | 1,512 | Memory allocation and heap entry points |
| `Source/OS/MemoryMgr/MemoryMgrInternal.a` | `$41045E–$410CBF` | 2,146 | Heap allocation, relocation, compaction, and purging |
| `Source/OS/MemoryMgr/BlockMove.a` | `$410CC0–$410F2F` | 624 | Overlapping memory copies |
| `Source/Toolbox/ToolboxEventMgr.a` | `$410F30–$4111AB` | 636 | Event delivery, journaling, activation, and FKeys |
| `Source/Toolbox/WindowMgr.a` | `$4111AC–$412197` | 4,076 | Window creation, drawing, visibility, and updates |
| `Source/Toolbox/MenuMgr.a` | `$412198–$412D53` | 3,004 | Menu creation, selection, drawing, and item updates |
| `Source/Toolbox/ControlMgr.a` | `$412D54–$413353` | 1,536 | Control creation, drawing, tracking, and disposal |
| `Source/Toolbox/ResourceMgr.a` | `$413354–$4148A7` | 5,460 | Resource maps, loading, writing, and compaction |
| `Source/Toolbox/DialogMgr.a` | `$4148A8–$415587` | 3,296 | Dialog creation, modal events, alerts, and item access |
| `Source/Toolbox/Munger.a` | `$415588–$415BDF` | 1,624 | String manipulation and fixed-point arithmetic |
| `Source/Toolbox/DeskMgr.a` | `$415BE0–$415ECB` | 748 | Desk accessory events, menus, and driver service |
| `Source/Toolbox/GetMgr.a` | `$415ECC–$41608D` | 450 | Windows, controls, menus, and resources from templates |
| `Source/Toolbox/TextEdit.a` | `$41608E–$416DAB` | 3,358 | Text layout, editing, selection, and scrolling |
| `Source/Toolbox/ScrapMgr.a` | `$416DAC–$416F8F` | 484 | Clipboard loading, storage, and transfer |
| `Source/Toolbox/PackageMgr.a` | `$416F90–$417051` | 194 | Package initialization and dispatch |
| `Source/Toolbox/SexyDate.a` | `$417052–$41712B` | 218 | Seconds and calendar conversion |
| `Source/OS/SCSIMgr.a` | `$41712C–$4175D1` | 1,190 | SCSI dispatch, transfers, and bus phases |
| `Source/OS/TimeMgr.a` | `$4175D2–$4176F7` | 294 | Timer installation, scheduling, and interrupts |
| `Source/Resources/ROMResourceMap.a` | `$4176F8–$417843` | 332 | Seventeen-resource map and names |
| `Source/Resources/PrintDriver.a` | `$417844–$4179B7` | 372 | Printer resource loading, map replacement, and dispatch |
| `Source/Resources/SoundDriver.a` | `$4179B8–$417D27` | 880 | Square-wave, four-tone, and free-form sound playback |
| `Source/Resources/Sony/Sony.a` | `$417D28–$418069` | 834 | Sony driver header, opening, and controls |
| `Source/Resources/Sony/SonyRWT.a` | `$41806A–$41859D` | 1,332 | Sony read/write requests, seeks, and completion |
| `Source/Resources/Sony/SonyUtil.a` | `$41859E–$418BDD` | 1,600 | Drive selection, seek, PWM, and disk VBL helpers |
| `Source/Resources/Sony/SonyRead.a` | `$418BDE–$418F2D` | 848 | Disk address and sector reading |
| `Source/Resources/Sony/SonyWrite.a` | `$418F2E–$4190C9` | 412 | Disk data and tag writing |
| `Source/Resources/Sony/SonyFormat.a` | `$4190CA–$4194D5` | 1,036 | Track formatting and nibble encoding |
| `Source/Resources/Sony/SonyDCD.a` | `$4194D6–$419D97` | 2,242 | DCD command, status, read, and write handling |
| `Source/Resources/ATP.a` | `$419D98–$41A6F1` | 2,394 | AppleTalk Transaction Protocol requests and responses |
| `Source/Resources/MPP.a` | `$41A6F2–$41B6C7` | 4,054 | AppleTalk link, datagram, and name-binding protocols |
| `Source/Resources/Serial/SerialDriver.a` | `$41B6C8–$41BF37` | 2,160 | Serial resource installation, I/O, and interrupt handling |
| `Source/Resources/StandardMDEF.a` | `$41BF38–$41C33D` | 1,030 | Menu resource, item selection, sizing, and drawing |
| `Source/Resources/StandardWDEF.a` | `$41C33E–$41C9D7` | 1,690 | Window resource, drawing, zooming, and hit testing |
| `Source/Resources/SANE/BinDec.a` | `$41C9D8–$41CF25` | 1,358 | Integer, binary, and decimal string conversions |
| `Source/Resources/SANE/Elems68K.a` | `$41CF26–$41DF8B` | 4,198 | Transcendental floating-point functions and coefficients |
| `Source/Resources/SANE/FP68K.a` | `$41DF8C–$41F14B` | 4,544 | Floating-point arithmetic and decimal conversions |
| `Source/Resources/Cursors.r` | `$41F14C–$41F27B` | 304 | Four cursor resources and memory headers |
| `Source/Resources/SystemFonts.r` | `$41F27C–$41FFBF` | 3,396 | Chicago font resources and memory headers |
| `Source/ROMTail.a` | `$41FFC0–$41FFCF` | 16 | SCSI reset helper |
| Hiram, configured in `target.json` | `$41FFD0–$41FFFF` | 48 | Initials, build date, and trailing date length |

QuickDraw forms one continuous span. Its sources include the original mask, slope, region, pattern, raster, and stretch tables. Its local `GrafTypes.a` holds declarations from the earlier QuickDraw source release. `Source/QuickDraw/CrossCheck.json` links the revised sources to that release and to the previous module hashes. The older evidence remains a historical record; the latest build records both module and include hashes. `target.json` lists each module, placement, and checked entry points. The matching evidence files describe each module's ancestors and restoration. Recorded addresses check the linked result; they do not supply symbol values to the assembler.

Filenames and module boundaries are reconstruction choices. `Points.a`, for example, comes from `QuickDraw/Classic/GrafAsm.m.a`. Matching bytes establish emitted code and data, but cannot establish the exact text or file organization of the lost sources. `StartInit.a` and `StartBoot.a` group the former startup fragments under names used in SuperMario. Older `Evidence/` snapshots retain the fragment paths, spans, and hashes recorded before that regrouping.

The source history helps explain several changes. The text renderer predates support for long font rows. PutRgn retains the rectangular-region bug fixed by later source. InstallRDrivers retains its earlier storage-handle check. SCSI retains its original error and transfer behavior. The corresponding evidence separates surviving code from instructions restored from the ROM.

The Font Manager now forms a continuous span from initialization through character-table construction. The resource map describes all 17 resources. Four cursor records match the released data unchanged. Chicago 12 differs from `Resources/SystemFonts.r` only in its final height-table bounds word, restored to `$FFFF`. MDEF, WDEF, and SANE packages 4, 5, and 7 also match their complete resource blocks. The printer, sound, Sony, ATP, MPP, and serial drivers also match their complete resource blocks. Startup includes the hardware tests, compressed icons, device search, boot-file loading, system alerts, and serial debugger.

Source-history dates can conflict with the ROM import filename. The filename says March 1986, but the ROM contains the PutPicRgn instruction described by an April 1986 history entry. That chronology remains unresolved; the instruction bytes match exactly.

## Build and verify

The build uses MPW Make, Asm, Rez, Link, and SC through the `mpw` emulator. Run from the project root:

```sh
python3 Tools/verify.py --require-complete
python3 -m unittest discover -s Tools -p 'test_*.py'
```

Install Python 3, `mpw`, `mpw-make`, and an MPW installation with its assembler, Rez compiler, linker, C compiler, headers, and libraries. The build uses no GNU m68k tools, Retro68 installation, or host C compiler. These environment variables select other installations:

| Variable | Purpose | Default |
| --- | --- | --- |
| `MPW` | MPW tools, headers, and libraries | `~/mpw` |
| `MPW_EXECUTABLE` | The `mpw` emulator | `mpw` on `PATH`, then `~/bin/mpw` |
| `MPW_MAKE_EXECUTABLE` | The shell that executes MPW Make's commands | `mpw-make` beside the emulator, on `PATH`, or in `~/bin` |
| `SUPER_MARIO_ROOT` | Surviving source tree used for provenance checks | `~/src/supermario/base/SuperMarioProj.1994-02-09` |

To prepare the sources and run MPW Make yourself:

```sh
python3 Tools/verify.py --prepare-only
cd Build
mpw-make -f Makefile
```

MPW `Make` emits the commands required to update its targets. `mpw-make` runs that tool and executes its output through the emulator's MPW shell. The generated Makefile runs Asm, Rez, Link, SC, ROMBuild, and Hiram. Its recipes do not invoke Python or a host compiler. Run the verifier again from the project root to compare the result with the reference ROM.

The preparation step keeps `Source/` in UTF-8 and writes MacRoman files with carriage-return line endings under `Build/`. It expands includes and macros, gives each manifest span one `PROC`, and renames local labels and equates to preserve their scope. It searches for quoted includes beside the including file, then in `Source/Includes/`. Include and conditional expansion reject cycles, malformed blocks, and unsupported syntax. The report records each dependency's hash.

The staged assembly uses `OPT NONE` around branches and long immediate operations on address registers, then restores `OPT SYNON`. This preserves the recorded instruction widths while accepting source synonyms elsewhere. Preparation also normalizes MOVEM register ranges and checks forward MOVEQ operands against the signed-byte range. Scoped `MACHINE MC68020` and `MACHINE MC68000` declarations retain the startup CPU probe and restore the normal instruction limit afterward. MPW imports and exports carry references between modules. Preparation does not assign ROM addresses to symbols. For short branches into the next object, it emits a byte displacement relative to that object and the current object's end. This avoids Asm's premature range check on unresolved imports. Link checks the signed-byte range, and verification checks that the object boundaries coincide.

MPW Asm runs with `-sym on,nolines -wb -l`. Omitting line records avoids an Asm object-file defect found in the ATP module. MPW Link joins the objects in manifest order into `Build/MacPlus-v3.rom`, a `ZROM` file containing resource `'ROM '` with ID zero. SC and Link build the ROMBuild and Hiram tools from their C sources.

Trap calls retain their `OPWORD` declarations and MPW options, such as `_NewPtr ,SYS,CLEAR` and `_Read ,ASYNC`. Asm combines the option bits with the base trap word. `GrafTraps.a` preserves the original QuickDraw trap macros from `QuickDraw/Classic/GrafTypes.m.a`.

The link reserves space for the compressed dispatch table in its ROM position and appends the 768 long offsets after the ROM prefix. ROMBuild reads symbol-derived layout metadata and compresses those offsets using the format documented in the surviving `OS/TrapDispatcher/Dispatch.a`. MPW Make adjusts the reservation and relinks until its size agrees with the encoded table, with a limit of 16 passes. ROMBuild then fills the reservation and writes `Build/MacPlus-v3.unfinished.bin`. All code retains its final linked position. The verifier independently decodes the compressed table, compares all offsets, and checks the compressed bytes against the reference. The generated dispatch `.uncompressed.bin` records the offsets before compression; its `.bin` file contains the ROM encoding.

SuperMario's `OS/DispTable.a` describes a post-link compressor and emits `handler-BaseOfROM` values. Its `Make/MainCode.Make` keeps that table last. A July 1986 note in `Interfaces/AIncludes/HardwareEqu.a` names `postlinker.a`; `OS/StartMgr/StartInit.a` supplies its trap count, and `OS/TrapDispatcher/Dispatch.a` retains the decoder. No implementation of PostLinker was found in the local release. The reservation and relinking used here adapt that process to the Plus table's position before QuickDraw; they do not claim to recover Apple's original build algorithm.

MPW Rez compiles the cursor and font `.r` files into resource forks. ROMBuild reads them through the Resource Manager and emits assembly in the resource order declared by `target.json`. Each resource receives an eight-byte memory header and exported labels; Asm then builds its object file. ROMBuild checks the resource set, IDs, names, and attributes before emitting data. The map source derives ROM offsets from those labels.

The surviving Rez sources already supply these payloads. `Source/Resources/Cursors.r` contains four unchanged resources from SuperMario's `Resources/ROMFonts.r`. `Source/Resources/SystemFonts.r` contains FONT 0 and FONT 12 from the surviving `Resources/SystemFonts.r`, with FONT 12's final word restored from `$0009` to `$FFFF`. The Chicago 12 in the later `ROMFonts.r` differs substantially. These local excerpts retain the resources needed by this ROM.

SuperMario's `Resources/Resources.make` compiles `ROMFonts.rsrc` with Rez. Its Hiram history records the addition of memory headers in February 1985; the surviving `buildRsrcImage` routine extracts resource payloads and adds those headers. That later Hiram uses a different ROM map format. ROMBuild supplies the Plus headers and linker labels here; Rez's resource-fork layout is only an intermediate representation.

Hiram reads the unfinished prefix, fills the tail from the linked prefix boundary with initials and the supplied date, and writes the checksum. It produces `Build/MacPlus-v3.hiram.bin`. The verifier compares every byte with the reference and independently checks the checksum before publishing `Build/MacPlus-v3.rebuilt.bin`. Neither ROMBuild nor Hiram reads the reference ROM or fills gaps in assembled code.

`Build/verification.json` records a successful verification. `Build/mpw-build.json` records Make's inputs, command, tool hashes, and outputs. The build directory also contains staged assembly, object files, assembler listings, `MacPlus-v3.map`, and Make's output logs. Source and output hashes invalidate stale objects and images, including changes that retain an old file timestamp. Unchanged preparation files keep their timestamps so MPW Make can reuse existing outputs. Failed MPW builds remove the finished images and their build records. Each verification run removes the prior verification report and verified image before checking the inputs.

The verifier checks module lengths, declared entry points, span boundaries, source inventories, and the reference image's hash and checksum. `--require-complete` requires every declared span through Hiram's fill boundary. The preparation code supports the constructs used by this reconstruction; extend it from the original syntax when another module needs a construct, and check the emitted bytes before accepting the change.

## Python tools

Python prepares the source files, starts MPW Make, and checks the resulting ROM. MPW Asm, Rez, Link, SC, ROMBuild, and Hiram produce the image. The generated Makefile does not invoke Python.

`verify.py` is the main command. It reads `target.json`, checks the reference ROM and historical source inventories, prepares the assembly, calls the build, and compares the output with the ROM. Preparation expands includes and macros, preserves procedure-local names, and controls instruction encodings for MPW Asm. This is more than a file-format conversion: it includes the assembler workarounds described above. After the build, the verifier checks module bytes, entry points, dispatch offsets, the checksum, and the complete image, then writes `Build/verification.json`.

The other modules support that command or the source study:

| Module | Role |
| --- | --- |
| `mpw_make.py` | Writes the MPW Makefile and resource layouts, stages inputs, tracks input and output hashes, invokes `mpw-make`, and records the build. The Makefile controls resource compilation and the dispatch-table relinking loop. |
| `mpw.py` | Resolves MPW tools and libraries, stages MacRoman text, and supplies shared C-tool compilation commands. It also reads the linked ROM resource and parses assembler listings and linker maps. Its assembly and C-tool helpers support focused tests. |
| `dispatch_table.py` | Independently encodes and decodes the trap table so verification can check the C ROMBuild tool's output. |
| `paths.py` | Resolves project and historical paths and checks source inventories, including the two recorded comment-header excerpts. |
| `index_sources.py` | Compares Ghidra symbol names with labels in the surviving sources and writes research candidates. It does not supply symbols to the linker. |
| `test_*.py` | Exercises preparation, MPW builds, relocation, dispatch compression, Hiram, provenance checks, and rejection of changed ROM bytes. |

QuickDraw uses the same preparation and verification path as the rest of the ROM. The former `verify_quickdraw.py` wrapper only ran the complete verifier and added a byte count, so it has been removed. Run `python3 Tools/verify.py --require-complete` to verify QuickDraw along with its dependencies. Include parsing tests live in `Tools/test_includes.py` and import `verify.expand_includes` directly.

## Shared includes and Hiram

`Source/Includes/` groups shared equates and trap words by their surviving include families. Modules retain their procedure-local values and import ROM entry points from their defining modules. `ROMStart` specifies the hardware mapping at `$400000`; routine and table locations come from the linker. Includes preserve applicable comments and identify their source files. The surviving includes contain later additions, so these reconstructed subsets do not claim to recover the exact lost include tree.

Hiram supplies the initials, date, trailing date length, and checksum. [Tools/hiram-notes.md](Tools/hiram-notes.md) records the adapted routines and MPW build. The date remains an explicit input so the output does not depend on the host clock or locale. The surviving `Tools/hiram.c` in the SuperMario tree remains unchanged.

The adaptation covers the Mac Plus finishing steps. It does not port the later resource loader, declaration data, encryption, or ROM slice output. The complete original initials string remains unknown; the build supplies the fragment visible in this ROM. Hiram's history records the older trailing-length date format, but its surviving implementation uses a later format.

## Evidence and source matching

`ROM/MacPlus-v3.bin` contains the 128 KB read from Ghidra's ROM block. Its SHA-256 is `dd908e2b65772a6b1f0c859c24e9a0d3dcde17b1c6a24f4abd8955846d7895e7`. The word sum from offset four through the end matches the stored checksum. `Evidence/snapshot.json` records the capture and file hashes.

`ghidra-symbols.tsv`, `ghidra-instructions.tsv`, and `ghidra-comments.json` preserve the existing analysis. Ghidra had no defined functions at capture time. Its labels and instruction boundaries remain analysis evidence; the byte comparison determines whether an assembled span matches. The capture scripts read the program without changing its analysis.

`source-candidates.tsv` maps 1,736 ROM addresses to source labels with the same name or a later `Trap` suffix. These are search candidates. Shared labels, patch files, and vector tables can produce several candidates for one address. The index does not count any of them as reconstructed code.

Regenerate the candidate index with:

```sh
python3 Tools/index_sources.py
```

The index verifies the 906 recorded assembly files before regenerating the candidate index. It preserves the captured inventory and ignores added reference files when that inventory exists. A separate resource inventory records the two released Rez files used here. Two assembly inventory entries, `TFSVOL.a` and `VSM.a`, describe copies with introductory comment headers removed. The verifier checks those recorded excerpts and reports the complete files' hashes separately. It rejects omitted instructions or changes to the retained text. Preserve these baselines when extending the reconstruction.

## Verification and limits

The complete build verifies every module, its declared entry points, and the final image. The tool tests cover source preparation, includes, MPW assembly, ROMBuild, Hiram, and image verification. The include tests formerly beside QuickDraw now live in `Tools/test_includes.py`. `Evidence/complete-build.json` and `Evidence/includes-and-hiram.json` record earlier build methods and their validation; [Evidence/mpw-build.json](Evidence/mpw-build.json) records the MPW build, all 131,072 matching bytes, and 74 passing tests. [Evidence/symbolic-linking.json](Evidence/symbolic-linking.json) records the move to linker symbols, all 5,142 checked entry points, and 79 passing tests. The latest reports live under `Build/`.

Binary identity establishes the reconstructed ROM contents. It does not recover the exact original spelling, module boundaries, or every private symbol name. Sources absent from the released tree, including several drivers, are restored from the ROM and marked accordingly. Surviving declarations, patch references, headers, and comments provide their documented provenance. Some source-history dates remain unresolved. The build tools run under the MPW emulator. The reconstructed ROM itself has not been tested by booting an emulator or Macintosh hardware.
