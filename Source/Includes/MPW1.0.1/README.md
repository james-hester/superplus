# MPW 1.0.1 headers

These 21 headers come from the MPW5 disk in the archive labeled “MPW 1.0.1 - 10 Oct 1986.” They retain the complete original text, including Apple's copyright notices, comments, spacing, and conditional assembly. The only conversions are MacRoman to UTF-8 and CR line endings to LF. MPW staging reverses those conversions for assembly.

The parent directory's includes select these files and supply missing declarations. They enable the original private-interface flags where the ROM needs them. Keep adaptations in those includes or in the consuming module so that these copies remain faithful to the disk files.

## Coverage

| Headers | Contents |
| --- | --- |
| `SysEqu`, `SysErr`, `HardwareEqu`, `Private`, `Traps` | System variables, errors, hardware, private interfaces, and traps |
| `FSEqu`, `FSPrivate` | File-system records and private HFS structures |
| `ATalkEqu`, `SonyEqu`, `SCSIEqu`, `TimeEqu` | AppleTalk, disk and SCSI drivers, and timer records |
| `ToolEqu`, `QuickEqu`, `PrEqu`, `SANEMacs`, `PackMacs` | Toolbox, QuickDraw, printing, numeric macros, and package interfaces |
| `FixMath`, `Graf3DEqu`, `ObjMacros`, `IntEnv`, `Signal` | Additional library and MPW tool interfaces, retained for reference |

The ROM uses headers through the parent includes; it does not include every file listed here. The disk's `Sample.a`, `Count.a`, and `Memory.a` are sample programs. `Stubs.a` supplies runtime code, `MakeFile.a` is a build file, and `Instructions.a` documents an example. Those files and the disk's binaries are outside this include collection.

## What the headers establish

`Private.a` defines `jClkNoMem` as `(595-512)*4+OSTable`. This explains the clock routine's vector address as a slot in the OS trap table. Its `HWCfgFlags` comments also identify the SCSI, new-clock, and extended-PRAM bits.

`FSPrivate.a` defines `LenBTCB` as 54 and `HFSStkLen` as 1280. These declarations replace constants we had reconstructed inside B-tree and startup code. The current filesystem subsets' 330 declarations all occur with the same expressions in the two 1986 filesystem headers.

`SysEqu.a` names the eight-byte area at `$9FA` `Scratch8`. The reconstructed Font Manager had called it `ScrapSize`; the actual `ScrapSize` variable is at `$960`. The Font Manager now uses `Scratch8`.

The font declarations also place the `FMDefaultSize` byte at `$987`. The ROM initializes it with a word store starting at `$986`, so that instruction now uses `FMDefaultSize-1` instead of redefining the field's address.

`SonyEqu.a` supplies the older `SonyExtra` field name and confirms `KHdSetTime=300`. Its shared record declarations replace repeated local layouts. One difference remains: the Plus ROM's Sony code uses a 12-byte embedded timer record, while the public `TimeEqu.a` declares 14 bytes. The Sony include retains the ROM's size before deriving its DCD offsets.

The complete headers also expose collisions hidden by the selected subsets. For example, AppleTalk's `ddpChecksum` is a record offset, while the reconstruction used `DDPChecksum` as a routine name. The routine receives a distinct name. This changes source names without changing the ROM bytes.

The original `SANEMacs.a` replaces the selected macro bodies in the SANE elementary functions. `OPT ALL` around each `FADDX` call lets Asm emit the ROM's `CLR.W` form for the zero selector. The four later `FBxxL` branch macro names return to their 1986 `FBxx` spellings.

## Provenance

[`Evidence/mpw-1.0.1-includes.json`](../../../Evidence/mpw-1.0.1-includes.json) records each disk path, original byte length and SHA-256, and converted byte length and SHA-256. The verifier checks the local copies against this inventory. The original disk directory is not a build dependency.
