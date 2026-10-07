import json
from pathlib import Path
import re
from struct import pack, unpack
import tempfile
import unittest

from dispatch_table import ENTRY_COUNT, encode_dispatch_table, decode_dispatch_table
from mpw_make import LINKED, MAP, build_project, linked_layout
import verify


class DispatchTableTests(unittest.TestCase):
    def test_signed_unsigned_absolute_and_unused_entries(self):
        values = [0, 0x10000, 0x100fc, 0x101fa, 0x181f8, 0x101f8, 0x101f8, 0, 0x101fa]
        values.extend([0] * (ENTRY_COUNT - len(values)))
        source = pack(">" + "I" * ENTRY_COUNT, *values)
        expected = bytes.fromhex("80 ff00010000 fe 007f 3fff 4000 ff000101f8 80 81")
        expected += b"\x80" * (ENTRY_COUNT - 9) + b"\0\0"
        if len(expected) & 1:
            expected += b"\0"
        self.assertEqual(encode_dispatch_table(source, 0x20000), expected)
        decoded, positions = decode_dispatch_table(expected, 0x20000)
        self.assertEqual(decoded, source)
        self.assertEqual(positions[:9], [0, 1, 6, 7, 9, 11, 13, 18, 19])

    def test_rejects_invalid_offsets_and_malformed_streams(self):
        with self.assertRaisesRegex(ValueError, "512 Toolbox"):
            encode_dispatch_table(b"\0" * (ENTRY_COUNT * 4 - 4), 0x20000)
        for bad in (3, 0x20000, 0xffffffff):
            data = pack(">I", bad) + b"\0" * (4 * (ENTRY_COUNT - 1))
            with self.assertRaisesRegex(ValueError, "Invalid dispatch ROM offset"):
                encode_dispatch_table(data, 0x20000)
        for stream in (b"\xff\0\0", b"\x01", b"\0\0", b"\x80" * 769,
                       bytes.fromhex("ff00000000"), bytes.fromhex("ff0001ffff"),
                       bytes.fromhex("7fff"), b"\x80" * 768 + b"\0\0\0\0"):
            with self.subTest(stream=stream[:8]), self.assertRaises(ValueError):
                decode_dispatch_table(stream, 0x20000)

    def test_rom_vectors_and_recompression(self):
        rom = (verify.HERE / "ROM/MacPlus-v3.bin").read_bytes()
        encoded = rom[0x7e58:0x82c6]
        source, positions = decode_dispatch_table(encoded, len(rom))
        values = unpack(">" + "I" * ENTRY_COUNT, source)
        self.assertEqual(values[0x50], 0x82c6)
        self.assertEqual(values[0x18], 0x15a56)
        self.assertEqual(values[512 + 0x2e], 0x10cc0)
        self.assertEqual(values[-1], 0x168c8)
        self.assertEqual(0x407e58 + positions[512], 0x40813b)
        self.assertEqual(encode_dispatch_table(source, len(rom)), encoded)

    def test_named_source_assembles_and_changed_handler_is_rejected(self):
        target = json.loads((verify.HERE / "target.json").read_text())
        modules = sorted(target["modules"], key=lambda item: int(item["start"], 16))
        module = next(item for item in modules if item.get("format") == "mpw-compressed-dispatch")
        rom = verify.source_path(target["rom"]["path"]).read_bytes()
        base = int(target["rom"]["base_address"], 16)
        with tempfile.TemporaryDirectory() as directory:
            build = Path(directory)
            translated = verify.project_assemblies(modules)
            for name, text in translated.items():
                verify.mpw.stage(build / (name + ".a"), text)

            def read_linked_table():
                layout = linked_layout(build)
                linked = verify.mpw.resource_data(build / LINKED)
                table = linked[layout["offsets_start"]:layout["metadata_start"]]
                offsets, size = verify.mpw.listing_symbols(build / (module["name"] + ".a.lst"))
                self.assertEqual(size, ENTRY_COUNT * 4)
                self.assertEqual(len(table), size)
                return table, offsets, verify.mpw.link_map(build / MAP)

            build_project(build, modules, target["postlink"])
            table, offsets, symbols = read_linked_table()
            result = verify.verify_emitted(module, table, offsets, translated[module["name"]],
                                           rom, base, build, symbols)
            self.assertEqual(result["dispatch_table"]["uncompressed_bytes"], 3072)
            self.assertEqual(unpack(">" + "I" * ENTRY_COUNT, table)[0x0d],
                             symbols["count1resources"] - symbols["baseofrom"])
            source = verify.source_path(module["source"]).read_text()
            source, count = re.subn(r"(?m)^(\s*ToolBox\s+\$00D,)\s*Count1Resources(\s*(?:;.*)?)$",
                                    r"\1Count1Resources+2\2", source)
            self.assertEqual(count, 1)
            path = build / "changed.a"
            path.write_text(source)
            changed_module = {**module, "source": str(path)}
            changed_modules = [changed_module if item["name"] == module["name"] else item
                               for item in modules]
            changed_assemblies = verify.project_assemblies(changed_modules)
            for name, text in changed_assemblies.items():
                verify.mpw.stage(build / (name + ".a"), text)
            changed_text = changed_assemblies[module["name"]]

            build_project(build, changed_modules, target["postlink"])
            changed_table, offsets, symbols = read_linked_table()
            self.assertEqual(unpack(">" + "I" * ENTRY_COUNT, changed_table)[0x0d],
                             symbols["count1resources"] - symbols["baseofrom"] + 2)
            self.assertNotEqual(changed_table, table)
            with self.assertRaisesRegex(ValueError, "first mismatches"):
                verify.verify_emitted(changed_module, changed_table, offsets, changed_text,
                                      rom, base, build, symbols)
