from hashlib import sha256
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import mpw
import test_mpw_make
import verify


class IncludeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.build = self.root / "build"
        self.build.mkdir()
        self.runner = mpw.executable()

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def assemble(self, source):
        assembly = verify.translate(source)
        binary, symbols = mpw.assemble(assembly, "probe", self.runner, self.build)
        return assembly, binary, symbols

    def test_native_nested_includes_preserve_source_and_record_dependencies(self):
        source = self.write("Module.a", "Main PROC\n\tINCLUDE 'Types.a'\n\tRTS\n\tENDP\n\tEND\n")
        self.write("Types.a", "\tDC.B 1,2\n\tINCLUDE 'Modes.a'\n\tDC.B 5,6\n")
        nested = self.write("Modes.a", "\tDC.B 3,4\n")
        assembly, binary, _ = self.assemble(source)
        self.assertEqual(binary, bytes.fromhex("0102030405064e75"))
        self.assertNotIn("DC.B", assembly)
        self.assertEqual({Path(name).name for name in assembly.dependencies},
                         {"Module.a", "Types.a", "Modes.a"})
        self.assertEqual(assembly.dependencies[str(nested)], sha256(nested.read_bytes()).hexdigest())
        staged = next(path for path in assembly.input_files if path.endswith("/Types.a"))
        self.assertEqual((self.build / "modules/probe" / staged).read_bytes(),
                         assembly.input_files[staged].replace("\n", "\r").encode("mac_roman"))

    def test_shared_search_keeps_local_precedence(self):
        source = self.write("local/Module.a", "\tINCLUDE 'Types.a'\nMain PROC\n\tMOVEQ #VALUE,D0\n\tENDP\n\tEND\n")
        shared = self.root / "shared"
        self.write("shared/Types.a", "\tINCLUDE 'Nested.a'\nVALUE EQU OTHER\n")
        self.write("shared/Nested.a", "OTHER EQU 2\n")
        with patch.object(verify, "SHARED_INCLUDES", shared):
            before, binary, _ = self.assemble(source)
            self.assertEqual(binary, bytes.fromhex("7002"))
            self.write("local/Types.a", "VALUE EQU 3\n")
            after, binary, _ = self.assemble(source)
        self.assertEqual(binary, bytes.fromhex("7003"))
        self.assertIn(str(shared / "Nested.a"), before.dependencies)
        self.assertNotIn(str(shared / "Types.a"), after.dependencies)

    def test_native_assembler_reports_missing_includes(self):
        source = self.write("Module.a", "\tINCLUDE 'Missing.a'\n\tEND\n")
        with self.assertRaises(subprocess.CalledProcessError) as error:
            self.assemble(source)
        self.assertIn("Unable to open", error.exception.stderr)
        self.assertIn("Missing.a", error.exception.stderr)

    def test_deleted_include_cannot_reuse_staged_copy(self):
        source = self.write("Module.a", "Main PROC\n\tINCLUDE 'RemovedValues.a'\n\tENDP\n\tEND\n")
        included = self.write("RemovedValues.a", "\tRTS\n")
        self.assemble(source)
        included.unlink()
        with self.assertRaises(subprocess.CalledProcessError) as error:
            self.assemble(source)
        self.assertIn("Unable to open", error.exception.stderr)

    def test_deleting_local_include_restores_shared_lookup(self):
        source = self.write("local/Module.a", "\tINCLUDE 'Types.a'\nMain PROC\n\tMOVEQ #VALUE,D0\n\tENDP\n\tEND\n")
        local = self.write("local/Types.a", "VALUE EQU 3\n")
        self.write("shared/Types.a", "VALUE EQU 7\n")
        with patch.object(verify, "SHARED_INCLUDES", self.root / "shared"):
            _, binary, _ = self.assemble(source)
            self.assertEqual(binary, bytes.fromhex("7003"))
            local.unlink()
            _, binary, _ = self.assemble(source)
        self.assertEqual(binary, bytes.fromhex("7007"))

    def test_native_assembler_skips_missing_include_in_false_conditional(self):
        source = self.write("Module.a", "\tIF 0 THEN\n\tINCLUDE 'Missing.a'\n\tENDIF\n"
                            "Main PROC\n\tRTS\n\tENDP\n\tEND\n")
        _, binary, _ = self.assemble(source)
        self.assertEqual(binary, bytes.fromhex("4e75"))

    def test_macro_selected_include_is_resolved_by_asm(self):
        source = self.write("Module.a", "\tGBLC &File\n&File SETC 'Types.a'\n\tINCLUDE &File\n"
                            "Main PROC\n\tMOVEQ #VALUE,D0\n\tENDP\n\tEND\n")
        included = self.write("Types.a", "VALUE EQU 7\n")
        assembly, binary, _ = self.assemble(source)
        self.assertEqual(binary, bytes.fromhex("7007"))
        self.assertIn(str(included), assembly.dependencies)

    def test_source_change_after_preparation_fails_before_staging(self):
        source = self.write("Module.a", "Main PROC\n\tRTS\n\tENDP\n\tEND\n")
        assembly = verify.translate(source)
        source.write_text(source.read_text().replace("RTS", "NOP"))
        with self.assertRaisesRegex(ValueError, "Source changed after preparation"):
            mpw.stage(self.build / "probe.a", assembly)

    def test_make_rebuilds_changed_native_include_with_preserved_timestamp(self):
        fixture = test_mpw_make.MPWMakeTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        source = self.write("Module.a", "Header PROC\n\tEXPORT BaseOfROM\nBaseOfROM\n"
                            "\tDC.L 0\n\tINCLUDE 'Value.a'\n\tENDP\n\tEND\n")
        included = self.write("Value.a", "\tDC.L $12345678\n")
        assembly = verify.translate(source, "rom_header")
        mpw.stage(fixture.build / "header.a", assembly)
        fixture.run_build()
        fixture.assert_image(0x12345678)
        old_object = (fixture.build / "header.o").read_bytes()
        other_timestamp = (fixture.build / "suffix.o").stat().st_mtime_ns
        staged_name = next(name for name in assembly.input_files if name.endswith("/Value.a"))
        staged = fixture.build / staged_name
        times = staged.stat()
        included.write_text("\tDC.L $76543210\n")
        mpw.stage(fixture.build / "header.a", verify.translate(source, "rom_header"))
        os.utime(staged, ns=(times.st_atime_ns, times.st_mtime_ns))
        fixture.run_build()
        fixture.assert_image(0x76543210)
        self.assertNotEqual((fixture.build / "header.o").read_bytes(), old_object)
        self.assertEqual((fixture.build / "suffix.o").stat().st_mtime_ns, other_timestamp)
        makefile = (fixture.build / "Makefile").read_bytes().decode("mac_roman")
        self.assertIn(":" + staged_name.replace("/", ":"), makefile)


if __name__ == "__main__":
    unittest.main()
