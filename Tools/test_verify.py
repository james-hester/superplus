import json
from pathlib import Path
import re
from struct import pack
import subprocess
import tempfile
import unittest

import verify
from paths import historical_path


class FidelityVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        target = json.loads((verify.HERE / "target.json").read_text())
        cls.modules = {module["name"]: module for module in target["modules"]}
        cls.rom = verify.source_path(target["rom"]["path"]).read_bytes()
        cls.base = int(target["rom"]["base_address"], 16)
        cls.mpw = verify.mpw.executable()
        if verify.sha256(cls.rom) != target["rom"]["sha256"]:
            raise ValueError("The test ROM differs from the recorded target.")

    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="rom-verifier-test-")
        self.addCleanup(directory.cleanup)
        self.build = Path(directory.name)

    def read_source(self, name):
        def include_fixture(source):
            lines = []
            for line in source.read_text().splitlines():
                include = re.fullmatch(r"\s+INCLUDE\s+'([^']+)'\s*(?:;.*)?", line, re.I)
                if include:
                    name = include[1].removeprefix(":").replace(":", "/")
                    candidates = (source.parent / name, verify.HERE / "Source/Includes" / name)
                    child = next(path for path in candidates if path.is_file())
                    lines.append(include_fixture(child))
                else:
                    lines.append(line)
            return "\n".join(lines) + "\n"

        return include_fixture(verify.source_path(self.modules[name]["source"]))

    def verify_copy(self, name, source, variant):
        path = self.build / (variant + ".a")
        path.write_text(source)
        module = {**self.modules[name], "name": variant, "source": str(path)}
        return verify.verify_module(module, self.rom, self.base, self.mpw, self.build)

    def assert_mutation_rejected(self, name, pattern, replacement):
        source = self.read_source(name)
        result = self.verify_copy(name, source, "original")
        self.assertTrue(result["matches_rom"])
        changed, count = re.subn(pattern, replacement, source, count=1, flags=re.MULTILINE)
        self.assertEqual(count, 1, "The mutation must alter an existing source statement.")
        self.assertNotEqual(source, changed)
        with self.assertRaisesRegex(ValueError, "first mismatches"):
            self.verify_copy(name, changed, "changed")
        original_bytes = (self.build / "original.bin").read_bytes()
        changed_bytes = (self.build / "changed.bin").read_bytes()
        self.assertEqual(len(original_bytes), len(changed_bytes))
        self.assertNotEqual(original_bytes, changed_bytes)

    def test_early_end_cannot_escape_byte_comparison(self):
        source = self.read_source("packagemgr")
        self.verify_copy("packagemgr", source, "original")
        with self.assertRaisesRegex(ValueError, "first mismatches"):
            self.verify_copy("packagemgr", "Short PROC\n\tRTS\n\tEND\n" + source, "early_end")

    def test_native_named_macro_parameters_preserve_argument_boundaries(self):
        source = self.build / "named_macro.a"
        source.write_text("""        MACRO
        Emit &num,&number
        IF &num = 0 THEN
        DC.B &number
        ELSE
        DC.B &num,&SysList[2]
        ENDIF
        ENDM
Data PROC
        Emit 0,$80
        Emit 2,$ff
        DC.B 0
        END
""")
        expected = bytes.fromhex("80 02 ff 00")
        module = {"name": "named_macro", "source": str(source),
                  "start": "0x400000", "end_exclusive": "0x400004"}
        self.assertTrue(verify.verify_module(module, expected, self.base, self.mpw, self.build)["matches_rom"])
        source.write_text(source.read_text().replace("Emit 0,$80", "Emit 0,UndefinedValue"))
        with self.assertRaises(subprocess.CalledProcessError) as failure:
            verify.verify_module(module, expected, self.base, self.mpw, self.build)
        self.assertEqual(failure.exception.cmd[1], "Asm")
        self.assertIn("Undefined id", failure.exception.output + failure.exception.stderr)

    def test_native_macro_variables_restore_machine_settings(self):
        source = self.build / "machine_macro.a"
        source.write_text("""        MACRO
        ProbeCache
        LCLC &SavedMachine
&SavedMachine SETC &Setting('MACHINE')
        MACHINE MC68020
        MOVEC D0,CACR
        MACHINE &SavedMachine
        ENDM
Start PROC
        ProbeCache
        RTS
        END
""")
        expected = bytes.fromhex("4e7b 0002 4e75")
        module = {"name": "machine_macro", "source": str(source),
                  "start": "0x400000", "end_exclusive": "0x400006"}
        self.assertTrue(verify.verify_module(module, expected, self.base, self.mpw, self.build)["matches_rom"])
        source.write_text(source.read_text().replace("        RTS", "        MOVEC D0,CACR"))
        with self.assertRaises(subprocess.CalledProcessError) as failure:
            verify.verify_module(module, expected, self.base, self.mpw, self.build)
        self.assertEqual(failure.exception.cmd[1], "Asm")

    def test_quoted_semicolons_survive_comment_parsing(self):
        source = self.build / "quoted_semicolons.a"
        source.write_text("""Data PROC
Table DC.B ';','it''s;data' ; actual comment
        END
""")
        expected = b";it's;data"
        module = {"name": "quoted_semicolons", "source": str(source),
                  "start": "0x400000", "end_exclusive": "0x40000a"}
        result = verify.verify_module(module, expected, 0x400000, self.mpw, self.build)
        self.assertTrue(result["matches_rom"])

    def test_column_one_comments_preserve_strings_and_location_expressions(self):
        source = self.build / "star_comments.a"
        source.write_text("""*R INCLUDE 'Missing.a'
* An ordinary MPW comment.
CommentTest PROC
Data DC.B '*R;notes' ; historical comment
Position EQU *
        DC.W 2*3,Position-Data
*R A note before the macro declaration.
        MACRO
        Emit &value
*R This note mentions &SysList[99] without referring to a macro argument.
        DC.W &value
        ENDM
        Emit 7
*R END
        RTS
        END
*R A trailing note's apostrophe.
""")
        expected = b"*R;notes" + bytes.fromhex("0006 0008 0007 4e75")
        module = {"name": "star_comments", "source": str(source),
                  "start": "0x400000", "end_exclusive": "0x400010"}
        self.assertTrue(verify.verify_module(module, expected, self.base, self.mpw, self.build)["matches_rom"])

    def test_native_opwords_preserve_trap_option_bits(self):
        source = self.build / "trap_options.a"
        source.write_text("""        INCLUDE 'Traps.a'
Calls PROC
        _NewPtr
        _NewPtr ,SYS
        _NewPtr ,CLEAR
        _NewPtr ,SYS,CLEAR
        _NewPtr ,SYS,SYS
        _NewHandle ,SYS,CLEAR
        _Read ,ASYNC
        _Write ,ASYNC
        _Control ,IMMED
        _Control ,ASYNC
        _CmpString ,MARKS,CASE
        _UprString ,MARKS
        _DrvrInstall ,SYS
        _DrvrInstall ,SYS,$100
        _ResrvMem ,SYS
        _PurgeMem ,SYS
        _SysError
        END
""")
        expected = bytes.fromhex("a11e a51e a31e a71e a51e a722 a402 a403 a204 "
                                 "a404 a63c a254 a43d a53d a440 a44d a9c9")
        module = {"name": "trap_options", "source": str(source),
                  "start": "0x400000", "end_exclusive": hex(0x400000 + len(expected))}
        self.assertTrue(verify.verify_module(module, expected, self.base, self.mpw, self.build)["matches_rom"])
        source.write_text(source.read_text().replace("_NewPtr ,SYS\n", "_NewPtr ,CLEAR\n"))
        with self.assertRaisesRegex(ValueError, "first mismatches"):
            verify.verify_module(module, expected, self.base, self.mpw, self.build)

    def test_historical_quickdraw_trap_macros(self):
        source = self.build / "quickdraw_traps.a"
        source.write_text("""        INCLUDE 'GrafTraps.a'
Calls PROC
        _MLongMul
        _MFixMul
        _MFixRatio
        _MSysError
        _GetScrnBits
        END
""")
        expected = bytes.fromhex("a867 a868 a869 a9c9 a833")
        module = {"name": "quickdraw_traps", "source": str(source),
                  "start": "0x400000", "end_exclusive": hex(0x400000 + len(expected))}
        self.assertTrue(verify.verify_module(module, expected, self.base, self.mpw, self.build)["matches_rom"])

    def test_native_assembler_rejects_unknown_directives(self):
        source = self.read_source("packagemgr")
        changed = "\t.data\n\tNOP\n\t.text\n" + source
        with self.assertRaises(subprocess.CalledProcessError) as failure:
            self.verify_copy("packagemgr", changed, "extra_section")
        self.assertEqual(failure.exception.cmd[1], "Asm")
        self.assertIn("Error", failure.exception.output + failure.exception.stderr)

    def test_instruction_mutation_is_rejected(self):
        self.assert_mutation_rejected("packagemgr", r"(MOVEQ\s+)#15,D0", r"\g<1>#14,D0")

    def test_equate_mutation_is_rejected(self):
        self.assert_mutation_rejected("packagemgr", r"(MapFalse\s+EQU\s+)\$FF00", r"\g<1>$FF01")

    def test_table_mutation_is_rejected(self):
        self.assert_mutation_rejected("sysutil", r"(DC\.B\s+)\('A'\),", r"\g<1>('B'),")

    def test_original_macro_body_changes_emitted_bytes(self):
        statement = "DC.B\t(&Syslst[1]+7)"
        self.assertIn(statement, historical_path("OS/SysUtil.a").read_text())
        self.assert_mutation_rejected(
            "sysutil", re.escape(statement), "DC.B\t(&Syslst[1]+6)"
        )

    def test_numeric_macro_arguments_follow_procedure_equates(self):
        source = self.build / "scoped_macro.a"
        source.write_text("""        MACRO
        _Return
        IF &Eval(&Syslst[1])=0 THEN
        MOVEQ #0,D0
        ELSEIF &Eval(&Syslst[1])<=8 THEN
        MOVEQ #&Syslst[1],D0
        ELSE
        MOVEQ #-1,D0
        ENDIF
        RTS
        ENDM
First PROC
paramSize EQU 4
FirstReturn _Return paramSize
Second PROC
paramSize EQU 8
SecondReturn _Return paramSize
        END
""")
        module = {"name": "scoped_macro", "source": str(source),
                  "start": "0x400002", "end_exclusive": "0x40000a",
                  "entry_points": {"FirstReturn": "0x400002", "SecondReturn": "0x400006"}}
        expected = bytes.fromhex("7004 4e75 7008 4e75")
        result = verify.verify_module(module, expected, 0x400002, self.mpw, self.build)
        self.assertTrue(result["matches_rom"])

    def test_conditions_select_bytes_and_scoped_constants(self):
        source = self.build / "conditions.a"
        source.write_text("""MODE EQU 1
        IF MODE THEN
        MACRO
        _Value
        IF &Eval(&SYSLIST[1]) = 4 THEN
        MOVEQ #4,D0
        ELSE
        MOVEQ #&Syslst[1],D0
        ENDIF
        ENDM
        ENDIF
        IF 0 THEN
MODE EQU 0
        MACRO
        _Value
        MOVEQ #-1,D0
        ENDM
        IF UndefinedFlag THEN
        InvalidOpcode
        ENDIF
        ENDIF
First PROC
VALUE EQU 4
        IF MODE THEN
        _Value VALUE
        ELSEIF 1/0 THEN
        InvalidOpcode
        ELSE
        InvalidOpcode
        ENDIF
Second PROC
VALUE EQU 8
        IF VALUE = 4 THEN
        InvalidOpcode
        ELSEIF VALUE = 8 THEN
        _Value VALUE
        ELSE
        InvalidOpcode
        ENDIF
        END
""")
        module = {"name": "conditions", "source": str(source),
                  "start": "0x400000", "end_exclusive": "0x400004"}
        expected = bytes.fromhex("7004 7008")
        result = verify.verify_module(module, expected, 0x400000, self.mpw, self.build)
        self.assertTrue(result["matches_rom"])
        source.write_text(source.read_text().replace("VALUE EQU 4", "VALUE EQU 5"))
        with self.assertRaisesRegex(ValueError, "first mismatches"):
            verify.verify_module(module, expected, 0x400000, self.mpw, self.build)

    def test_native_assembler_rejects_malformed_conditions(self):
        for index, text in enumerate((" ELSE", " ENDIF", " ELSEIF 1 THEN")):
            with self.subTest(text=text):
                source = self.build / ("bad_condition_" + str(index) + ".a")
                source.write_text("Start PROC\n" + text + "\n NOP\n END\n")
                with self.assertRaises(subprocess.CalledProcessError) as failure:
                    verify.mpw.assemble(verify.translate(source), source.stem, self.mpw, self.build)
                self.assertEqual(failure.exception.cmd[1], "Asm")

    def test_leading_zero_constants_remain_decimal(self):
        source = self.build / "decimal.a"
        source.write_text("A EQU 08\nB EQU 09\nC EQU 010\nData PROC\n\tIF C=10 THEN\n\tDC.W A,B,C,$0010\n\tENDIF\n\tEND\n")
        module = {"name": "decimal", "source": str(source),
                  "start": "0x400000", "end_exclusive": "0x400008"}
        expected = bytes.fromhex("0008 0009 000a 0010")
        self.assertTrue(verify.verify_module(module, expected, 0x400000, self.mpw, self.build)["matches_rom"])

    def test_unsized_index_register_uses_word_encoding(self):
        source = self.build / "word_index.a"
        source.write_text("Start PROC\n\tMOVE.W 0(A0,D0),D1\n\tRTS\n\tEND\n")
        module = {"name": "word_index", "source": str(source),
                  "start": "0x400002", "end_exclusive": "0x400008"}
        expected = bytes.fromhex("3230 0000 4e75")
        result = verify.verify_module(module, expected, 0x400002, self.mpw, self.build)
        self.assertTrue(result["matches_rom"])

    def test_byte_strings_preserve_commas_case_and_mac_roman(self):
        source = self.build / "strings.a"
        source.write_text("Text PROC\n\tDC.B '© Apple, 1985',('A'+1),'can''t',0\n\tEND\n")
        expected = "© Apple, 1985Bcan't".encode("mac_roman") + b"\0"
        module = {"name": "strings", "source": str(source), "start": "0x400000",
                  "end_exclusive": hex(0x400000 + len(expected))}
        result = verify.verify_module(module, expected, 0x400000, self.mpw, self.build)
        self.assertTrue(result["matches_rom"])

    def test_original_labels_can_overlap_optional_register_names(self):
        source = self.build / "register_names.a"
        source.write_text("Block PROC\n\tBRA.S AC\nTable DC.W AC-Table,BC-Table,Control-Table,Status-Table\nAC RTS\nBC RTS\nControl RTS\nStatus RTS\n\tEND\n")
        expected = bytes.fromhex("6008 0008 000a 000c 000e 4e75 4e75 4e75 4e75")
        module = {"name": "register_names", "source": str(source), "start": "0x400000",
                  "end_exclusive": "0x400012"}
        result = verify.verify_module(module, expected, 0x400000, self.mpw, self.build)
        self.assertTrue(result["matches_rom"])

    def link_source_modules(self, name, sources):
        directory = self.build / name
        directory.mkdir()
        modules = []
        for module, text in sources:
            source = directory / (module + ".source.a")
            source.write_text(text)
            modules.append({"name": module, "source": str(source)})
        assemblies = verify.project_assemblies(modules)
        objects = []
        for module, _ in sources:
            verify.mpw.stage(directory / (module + ".a"), assemblies[module])
            verify.mpw.run(self.mpw, "Asm", ["-i", verify.mpw.ASM_INCLUDE_PATH,
                           "-sym", "on,nolines", "-wb", "-l", "-o",
                           module + ".o", module + ".a"], directory)
            objects.append(module + ".o")
        listing, diagnostics = verify.mpw.run(self.mpw, "Link", ["-t", "ZROM", "-rt", "ROM =0",
                                               "-la", "-o", "linked.rom", *objects], directory)
        self.assertEqual(diagnostics.strip(), "")
        (directory / "linked.map").write_text(listing)
        return (verify.mpw.resource_data(directory / "linked.rom"),
                verify.mpw.link_map(directory / "linked.map"))

    def test_external_references_follow_exported_target_when_layout_changes(self):
        header = """Header PROC
        EXPORT BaseOfROM
BaseOfROM EQU *
        DC.L 0
        ENDP
        END
"""
        caller = """ROMStart EQU $400000
Caller PROC
        IMPORT Target,BaseOfROM
        EXPORT CallStart,Pointer,Offset
CallStart
        BSR.W Target
        JSR Target
        LEA Target,A0
Pointer DC.L Target-BaseOfROM+ROMStart
Offset DC.L Target-BaseOfROM
        RTS
        ENDP
        END
"""
        target = """TargetModule PROC
        EXPORT Target
Target RTS
        ENDP
        END
"""
        for padding in (0, 8):
            with self.subTest(padding=padding):
                sources = [("header", header), ("caller", caller)]
                if padding:
                    sources.append(("padding", "Padding PROC\n" + "\tNOP\n" * (padding // 2)
                                    + "\tENDP\n\tEND\n"))
                sources.append(("target", target))
                image, symbols = self.link_source_modules("layout_" + str(padding), sources)
                target_offset = 26 + padding
                expected = bytes(4) + pack(">6H2IH", 0x6100, target_offset - 6,
                    0x4eba, target_offset - 10, 0x41fa, target_offset - 14,
                    0x400000 + target_offset, target_offset, 0x4e75)
                expected += bytes.fromhex("4e71") * (padding // 2) + bytes.fromhex("4e75")
                self.assertEqual(image, expected)
                self.assertEqual(symbols["baseofrom"], 0)
                self.assertEqual(symbols["target"], target_offset)
                self.assertEqual(symbols["callstart"], 4)
                self.assertEqual(symbols["pointer"], 16)
                self.assertEqual(symbols["offset"], 20)

    def test_procedure_exports_keep_local_labels_and_equates_separate(self):
        caller = """Caller PROC
        IMPORT First,Second
        BSR.W First
        BSR.W Second
        RTS
        ENDP
        END
"""
        provider = """First PROC EXPORT
Value EQU 1
Loop MOVEQ #Value,D0
        BRA.S Exit
        NOP
Exit RTS
        ENDP
Second PROC EXPORT
Value EQU 2
Loop MOVEQ #Value,D0
        BRA.S Exit
        NOP
Exit RTS
        ENDP
        END
"""
        image, symbols = self.link_source_modules("procedure_exports",
                                                 [("caller", caller), ("provider", provider)])
        self.assertEqual(image, bytes.fromhex(
            "6100 0008 6100 000c 4e75 7001 6002 4e71 4e75 7002 6002 4e71 4e75"))
        self.assertEqual(symbols["first"], 10)
        self.assertEqual(symbols["second"], 18)

    def test_late_short_import_uses_explicit_native_boundary_expression(self):
        caller = ("Caller PROC\n\tIMPORT Target,Following\n\tEXPORT CallSite,CallerEnd\n"
                  + "\tNOP\n" * 128
                  + "CallSite DC.B $61,Target-Following+CallerEnd-(*+2)\n"
                  + "\tRTS\nCallerEnd\n\tENDP\n\tEND\n")

        def sources(padding, body=caller):
            following = ("Following PROC EXPORT\n\tEXPORT Target\n" + "\tNOP\n" * (padding // 2)
                         + "Target RTS\n\tENDP\n\tEND\n")
            return [("caller", body), ("following", following)]

        for padding in (0, 124):
            with self.subTest(padding=padding):
                image, symbols = self.link_source_modules("late_short_" + str(padding), sources(padding))
                expected = (bytes.fromhex("4e71") * 128 + bytes([0x61, 2 + padding])
                            + bytes.fromhex("4e75") + bytes.fromhex("4e71") * (padding // 2)
                            + bytes.fromhex("4e75"))
                self.assertEqual(image, expected)
                self.assertEqual(symbols["callsite"], 256)
                self.assertEqual(symbols["target"] - symbols["callsite"] - 2, 2 + padding)
                self.assertEqual(symbols["callerend"], symbols["following"])

        with self.assertRaises(subprocess.CalledProcessError) as failure:
            self.link_source_modules("late_short_out_of_range", sources(126))
        self.assertEqual(failure.exception.cmd[1], "Link")
        direct = caller.replace("DC.B $61,Target-Following+CallerEnd-(*+2)", "BSR.S Target")
        with self.assertRaises(subprocess.CalledProcessError) as failure:
            self.link_source_modules("late_short_unresolved", sources(0, direct))
        self.assertEqual(failure.exception.cmd[1], "Asm")

    def test_local_pc_equates_preserve_instruction_data_addresses(self):
        for name, equate in (("location", "*+2"), ("label", "DefWordBrk+2")):
            source = self.build / (name + ".a")
            source.write_text(f"""TextEdit PROC
{"lo16 EQU " + equate if name == "location" else ""}
DefWordBrk AND.L #$0000FFFF,D0
{"lo16 EQU " + equate if name == "label" else ""}
        MOVE.W lo16,D1
        DC.W 2*3,2 * 3
        END
""")
            expected = bytes.fromhex("0280 0000 ffff 323a fffa 0006 0006")
            module = {"name": name, "source": str(source), "start": "0x416000",
                      "end_exclusive": "0x41600e"}
            result = verify.verify_module(module, expected, 0x416000, self.mpw, self.build)
            self.assertTrue(result["matches_rom"])

    def test_cpu_probe_can_restore_the_68000_instruction_limit(self):
        source = self.build / "cpu_probe.a"
        source.write_text("""ProbeCode PROC
        MACHINE MC68020
Probe MOVEC D0,CACR
        MACHINE MC68000
        RTS
        END
""")
        expected = bytes.fromhex("4e7b 0002 4e75")
        module = {"name": "cpu_probe", "source": str(source), "start": "0x400594",
                  "end_exclusive": "0x40059a"}
        result = verify.verify_module(module, expected, 0x400594, self.mpw, self.build)
        self.assertTrue(result["matches_rom"])
        source.write_text(source.read_text().replace("        RTS", "        MOVEC D0,CACR"))
        with self.assertRaises(subprocess.CalledProcessError):
            verify.verify_module(module, expected, 0x400594, self.mpw, self.build)

    def test_rez_resources_build_headers_and_preserve_order(self):
        source = self.build / "resources.r"
        source.write_text('''/* data 'FAKE' (0) {}; */
data 'FONT' (0, "Chicago", sysheap) {
};
data 'CURS' (2, sysheap, locked) { $"AA 55" /* .. */ };''')
        module = {"name": "resources", "source": str(source), "format": "rez-data",
                  "start": "0x41f14c", "end_exclusive": "0x41f15e", "block_flags": "0xc0",
                  "first_master_pointer_offset": "0x80", "resources": [
                      {"type": "CURS", "id": 2, "label": "Curs2", "attributes": ["sysheap", "locked"]},
                      {"type": "FONT", "id": 0, "label": "Font0", "name": "Chicago", "attributes": ["sysheap"]}],
                  "entry_points": {"Curs2": "0x41f154", "Font0": "0x41f15e"}}
        expected = bytes.fromhex("c000000a 00000080 aa55 c0000008 00000084")
        self.assertTrue(verify.verify_module(module, expected, 0x41f14c, self.mpw, self.build)["matches_rom"])
        source.write_text(source.read_text().replace("AA 55", "AA 56"))
        with self.assertRaisesRegex(ValueError, "first mismatches"):
            verify.verify_module(module, expected, 0x41f14c, self.mpw, self.build)

    def test_include_changes_affect_bytes_and_dependency_hashes(self):
        source = self.build / "include.a"
        included = self.build / "Types.a"
        source.write_text("\tINCLUDE 'Types.a'\nStart PROC\n\tMOVEQ #VALUE,D0\n\tRTS\n\tEND\n")
        included.write_text("VALUE EQU 4\n")
        module = {"name": "include", "source": str(source), "start": "0x400000",
                  "end_exclusive": "0x400004"}
        expected = bytes.fromhex("7004 4e75")
        before = verify.verify_module(module, expected, 0x400000, self.mpw, self.build)
        dependencies = {item["path"]: item["sha256"] for item in before["source_dependencies"]}
        self.assertEqual(dependencies[str(included.resolve())], verify.sha256(included.read_bytes()))
        included.write_text("VALUE EQU 5\n")
        with self.assertRaisesRegex(ValueError, "first mismatches"):
            verify.verify_module(module, expected, 0x400000, self.mpw, self.build)
        after = verify.verify_module(module, bytes.fromhex("7005 4e75"), 0x400000, self.mpw, self.build)
        self.assertEqual(before["source_sha256"], after["source_sha256"])
        self.assertNotEqual(before["source_dependencies"], after["source_dependencies"])

    def test_native_assembler_stops_at_end(self):
        source = self.build / "include.a"
        source.write_text("Start PROC\n\tRTS\n\tEND\n\tINCLUDE 'Types.a'\n")
        (self.build / "Types.a").write_text("\tInvalidOpcode\n")
        module = {"name": "end", "source": str(source), "start": "0x400000",
                  "end_exclusive": "0x400002"}
        result = verify.verify_module(module, bytes.fromhex("4e75"), self.base, self.mpw, self.build)
        self.assertTrue(result["matches_rom"])

    def test_postlink_checksum_exception_is_limited_to_zero_at_rom_base(self):
        source = self.build / "header.a"
        source.write_text("Header PROC\nCheckSum DC.L 0\nStart DC.W $1234\n\tEND\n")
        module = {"name": "header", "source": str(source), "start": "0x400000",
                  "end_exclusive": "0x400006", "postlink_checksum": True}
        rom = bytes.fromhex("deadbeef 1234")
        result = verify.verify_module(module, rom, self.base, self.mpw, self.build)
        self.assertEqual(result["verified_bytes"], 2)
        self.assertFalse(result["matches_rom"])
        source.write_text("Header PROC\nCheckSum DC.L 1\nStart DC.W $1234\n\tEND\n")
        with self.assertRaisesRegex(ValueError, "zero longword at the ROM base"):
            verify.verify_module(module, rom, self.base, self.mpw, self.build)
        source.write_text("Header PROC\nCheckSum DC.L 0\nStart DC.W $1235\n\tEND\n")
        with self.assertRaisesRegex(ValueError, "first mismatches"):
            verify.verify_module(module, rom, self.base, self.mpw, self.build)
        with self.assertRaisesRegex(ValueError, "zero longword at the ROM base"):
            verify.verify_module({**module, "start": "0x400002", "end_exclusive": "0x400008"},
                                 rom + b"\0\0", self.base, self.mpw, self.build)



if __name__ == "__main__":
    unittest.main()
