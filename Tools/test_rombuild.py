from pathlib import Path
import random
from struct import pack
import subprocess
import tempfile
import unittest

from dispatch_table import ENTRY_COUNT, decode_dispatch_table, encode_dispatch_table
from mpw import build_tool


class ROMBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compiler_directory = tempfile.TemporaryDirectory(prefix="rombuild-compiler-")
        cls.addClassCleanup(cls.compiler_directory.cleanup)
        tool = build_tool("rombuild", cls.compiler_directory.name)
        cls.mpw = tool["runner"][0]
        cls.rombuild = tool["executable"]

    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="rombuild-test-")
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)

    def package(self, data, *, offset=8, size=0x20000, resource_type="ROM ", resource_id=0, layout=False):
        source = self.directory / "input.r"
        resource = self.directory / "input.rsrc"
        output = self.directory / "output.bin"
        resource.unlink(missing_ok=True)
        output.unlink(missing_ok=True)
        lines = [f"data '{resource_type}' ({resource_id}) {{"]
        lines.extend('    $"' + data[i:i + 32].hex() + '"' for i in range(0, len(data), 32))
        lines.append("};")
        source.write_bytes(("\r".join(lines) + "\r").encode("ascii"))
        subprocess.run([self.mpw, "Rez", source.name, "-o", resource.name],
                       cwd=self.directory, check=True, capture_output=True, encoding="mac_roman")
        options = (["--resolve-layout", "DispatchSize.a", "--status-file", "DispatchStatus"]
                   if layout else ["--dispatch-offset", str(offset)])
        result = subprocess.run([self.mpw, str(self.rombuild), *options,
                                 "--rom-size", str(size), resource.name, output.name],
                                cwd=self.directory, capture_output=True, encoding="mac_roman")
        return result, output

    def test_encoding_forms_preserve_prefix_and_suffix(self):
        values = [0, 0x10000, 0x100fc, 0x101fa, 0x181f8, 0x101f8, 0x101f8, 0, 0x101fa]
        values.extend([0] * (ENTRY_COUNT - len(values)))
        table = pack(">" + "I" * ENTRY_COUNT, *values)
        prefix, suffix = b"\0HEAD\xff\x80\x0a", b"\xff\0TAIL\x0d\x0a"
        result, output = self.package(prefix + table + suffix)
        self.assertEqual(result.returncode, 0, result.stderr)
        encoded = encode_dispatch_table(table, 0x20000)
        self.assertEqual(output.read_bytes(), prefix + encoded + suffix)
        self.assertEqual(decode_dispatch_table(encoded, 0x20000)[0], table)

    def test_varied_tables_match_the_existing_encoder(self):
        random_values = random.Random(68000)
        for case in range(4):
            values = [random_values.randrange(0, 0x20000, 2) for _ in range(ENTRY_COUNT)]
            values[::7] = [0] * len(values[::7])
            table = pack(">" + "I" * ENTRY_COUNT, *values)
            with self.subTest(case=case):
                result, output = self.package(b"PREFIX00" + table + b"SUFFIX")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(output.read_bytes(),
                                 b"PREFIX00" + encode_dispatch_table(table, 0x20000) + b"SUFFIX")

    def test_invalid_dispatch_data_creates_no_output(self):
        table = bytes(ENTRY_COUNT * 4)
        cases = [
            (b"PREFIX00" + table[:-1], {}, "outside"),
            (b"PREFIX00" + table, {"offset": 9}, "outside"),
            (b"PREFIX00" + table, {"offset": 0xffffffff}, "outside"),
            (b"PREFIX00" + table, {"size": 16}, "exceeds ROM size"),
            (b"PREFIX00" + pack(">I", 3) + table[4:], {}, "invalid dispatch"),
            (b"PREFIX00" + pack(">I", 0x20000) + table[4:], {}, "invalid dispatch"),
            (b"PREFIX00" + pack(">I", 0xffffffff) + table[4:], {}, "invalid dispatch"),
        ]
        for data, options, message in cases:
            with self.subTest(options=options, message=message):
                result, output = self.package(data, **options)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertFalse(output.exists())

    def test_requires_the_named_resource_and_nonempty_code(self):
        for options, data, message in [
            ({"resource_type": "TEST"}, bytes(3072), "resource 'ROM ' with ID 0"),
            ({"resource_id": 1}, bytes(3072), "resource 'ROM ' with ID 0"),
            ({}, b"", "resource is empty"),
        ]:
            with self.subTest(options=options):
                result, output = self.package(data, **options)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertFalse(output.exists())

    def test_layout_mode_requests_relink_and_then_patches_reserved_bytes(self):
        table = pack(">I", 800) + bytes((ENTRY_COUNT - 1) * 4)
        encoded = encode_dispatch_table(table, 0x20000)
        for reserved in (770, len(encoded)):
            prefix = b"PREFIX00" + bytes(reserved) + b"SUFFIX00"
            metadata = pack(">7I", 0x52424c44, 1, 8, 8 + reserved,
                            len(prefix), len(prefix), ENTRY_COUNT)
            result, output = self.package(prefix + table + metadata, layout=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            changed = reserved != len(encoded)
            status = (self.directory / "DispatchStatus").read_text()
            self.assertIn(f"Set DispatchChanged {int(changed)}", status)
            self.assertIn(f"Set ROMPrefixSize {len(prefix)}", status)
            if changed:
                self.assertFalse(output.exists())
                self.assertIn(f"DispatchBytes EQU {len(encoded)}",
                              (self.directory / "DispatchSize.a").read_text())
            else:
                self.assertEqual(output.read_bytes(), b"PREFIX00" + encoded + b"SUFFIX00")

    def test_layout_mode_rejects_missing_metadata_and_invalid_bounds(self):
        prefix = bytes(8 + 770 + 8)
        table = bytes(ENTRY_COUNT * 4)
        fields = [0x52424c44, 1, 8, 778, len(prefix), len(prefix), ENTRY_COUNT]
        cases = [(prefix + table, "metadata")]
        for index, value in ((0, 0), (1, 2), (2, 7), (3, len(prefix) + 2),
                             (4, len(prefix) + 2), (5, len(prefix) + 2), (6, ENTRY_COUNT - 1)):
            changed = fields.copy()
            changed[index] = value
            cases.append((prefix + table + pack(">7I", *changed), "layout"))
        for data, message in cases:
            with self.subTest(message=message, data=data[-28:]):
                result, output = self.package(data, layout=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertFalse(output.exists())


    def resource_assembly(self, source_text, layout_text):
        source = self.directory / "resources.r"
        resource = self.directory / "resources.rsrc"
        layout = self.directory / "resources.layout"
        output = self.directory / "resources.a"
        source.write_bytes(source_text.replace("\n", "\r").encode("mac_roman"))
        layout.write_bytes(layout_text.replace("\n", "\r").encode("ascii"))
        resource.unlink(missing_ok=True)
        output.write_bytes(b"stale output")
        subprocess.run([self.mpw, "Rez", source.name, "-o", resource.name],
                       cwd=self.directory, check=True, capture_output=True, encoding="mac_roman")
        result = subprocess.run([self.mpw, str(self.rombuild), "--resources", layout.name,
                                 resource.name, output.name], cwd=self.directory,
                                capture_output=True, encoding="mac_roman")
        return result, output

    def test_resource_mode_rebuilds_plus_cursors_in_layout_order(self):
        from mpw import assemble

        root = Path(__file__).resolve().parent.parent
        source = (root / "Source/Resources/Cursors.r").read_text()
        layout = "rom_cursors 192 128 4\n" + "".join(
            f"43555253 {number} 80 Curs{number} -\n" for number in (2, 3, 1, 4))
        result, output = self.resource_assembly(source, layout)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = output.read_bytes()
        subprocess.run([self.mpw, "Asm", "-o", "generated.o", output.name],
                       cwd=self.directory, check=True, capture_output=True, encoding="mac_roman")
        assembly = data.decode("mac_roman").replace("\r", "\n")
        binary, labels = assemble(assembly, "cursors", self.mpw, self.directory)
        reference = (root / "ROM/MacPlus-v3.bin").read_bytes()
        self.assertEqual(binary, reference[0x1f14c:0x1f27c])
        for index, number in enumerate((2, 3, 1, 4)):
            self.assertEqual(labels[f"curs{number}block"], index * 76)
            self.assertEqual(labels[f"curs{number}"], index * 76 + 8)
            self.assertEqual(labels[f"curs{number}end"], (index + 1) * 76)
            self.assertIn(f"EXPORT Curs{number},Curs{number}Block,Curs{number}End", assembly)

    def test_resource_mode_preserves_empty_named_font(self):
        from mpw import assemble

        root = Path(__file__).resolve().parent.parent
        source = (root / "Source/Resources/SystemFonts.r").read_text()
        layout = ("rom_fonts 192 144 2\n464f4e54 0 64 Font0 4368696361676f\n"
                  "464f4e54 12 64 Font12 -\n")
        result, output = self.resource_assembly(source, layout)
        self.assertEqual(result.returncode, 0, result.stderr)
        assembly = output.read_bytes().decode("mac_roman").replace("\r", "\n")
        binary, labels = assemble(assembly, "fonts", self.mpw, self.directory)
        reference = (root / "ROM/MacPlus-v3.bin").read_bytes()
        self.assertEqual(binary, reference[0x1f27c:0x1ffc0])
        self.assertEqual(labels["font0"], labels["font0end"])
        self.assertEqual(labels["font0end"], labels["font12block"])
        self.assertEqual(binary[:16], pack(">4I", 0xc0000008, 144, 0xc0000d3c, 148))

    def test_resource_mode_does_not_pad_odd_payloads(self):
        from mpw import assemble

        source = "data 'TEST' (-32768) { $\"01\" };\ndata 'TEST' (32767) { $\"020304\" };\n"
        layout = "rom_odd 192 0 2\n54455354 -32768 0 First -\n54455354 32767 0 Second -\n"
        result, output = self.resource_assembly(source, layout)
        self.assertEqual(result.returncode, 0, result.stderr)
        assembly = output.read_bytes().decode("mac_roman").replace("\r", "\n")
        binary, labels = assemble(assembly, "odd", self.mpw, self.directory)
        self.assertEqual(binary, pack(">2I", 0xc0000009, 0) + b"\x01" +
                         pack(">2I", 0xc000000b, 4) + b"\x02\x03\x04")
        self.assertEqual(labels["secondblock"], 9)

    def test_resource_mode_rejects_metadata_changes_and_unlisted_resources(self):
        source = 'data \'TEST\' (1, "Name", sysheap) { $"0102" };\n'
        valid = "rom_resources 192 0 1\n54455354 1 64 Item 4e616d65\n"
        cases = [
            (valid.replace("1 64", "2 64"), "missing resource"),
            (valid.replace("1 64", "1 0"), "attributes"),
            (valid.replace("4e616d65", "-"), "name"),
            (valid.replace("4e616d65", "4e616d6564"), "name"),
            (valid.replace("54455354", "464f4e54"), "missing resource"),
        ]
        for layout, message in cases:
            with self.subTest(layout=layout):
                result, output = self.resource_assembly(source, layout)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertFalse(output.exists())
        result, output = self.resource_assembly(source + "data 'MORE' (0) {};\n", valid)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("resource count", result.stderr)
        self.assertFalse(output.exists())

    def test_resource_mode_rejects_invalid_layout_and_symbol_collisions(self):
        source = "data 'TEST' (1) {};\ndata 'TEST' (2) {};\n"
        valid = "rom_resources 192 0 2\n54455354 1 0 First -\n54455354 2 0 Second -\n"
        cases = [
            "",
            valid.replace("192", "256"),
            valid.replace("192 0", "192 1"),
            valid.replace("192 0", "192 4294967296"),
            valid.replace("192 0", "192 4294967292"),
            valid.replace("0 2\n", "0 0\n", 1),
            valid.replace("0 2\n", "0 32768\n", 1),
            valid.replace("0 2\n", "0 -1\n", 1),
            valid.replace("0 2\n", "0 1\n", 1),
            valid.replace("54455354", "TEST", 1),
            valid.replace("54455354", "5445535g", 1),
            valid.replace("1 0 First", "32768 0 First"),
            valid.replace("1 0 First", "-32769 0 First"),
            valid.replace("1 0 First", "- 0 First"),
            valid.replace("1 0 First", "1 256 First"),
            valid.replace("First", "bad-label"),
            valid.replace("First", "1First"),
            valid.replace("First", "A" * 64),
            valid.replace("First", "rom_resources"),
            valid.replace("Second", "first"),
            valid.replace("Second", "FirstBlock"),
            valid.replace("2 0 Second", "1 0 Second"),
            valid.replace("First -", "First 1"),
            valid.replace("First -", "First gg"),
            valid.replace("First -", "First " + "41" * 256),
            valid.replace("First -", "First - unexpected"),
            valid.replace("First -", "First"),
            valid.replace("First -", "First -\0ignored"),
            valid.splitlines()[0] + "\n",
            valid + "\n",
        ]
        for layout in cases:
            with self.subTest(layout=layout):
                result, output = self.resource_assembly(source, layout)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
