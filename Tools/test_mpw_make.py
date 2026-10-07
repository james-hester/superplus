import os
from pathlib import Path
from struct import pack
import tempfile
import unittest

import mpw
from dispatch_table import decode_dispatch_table
from mpw_make import FINAL, LINKED, MAP, STATE, UNFINISHED, build_project, fingerprints


class MPWMakeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="mpw-make-test-")
        self.addCleanup(directory.cleanup)
        self.build = Path(directory.name)
        self.values = [0, 0x10000, 0x10002, 0x10000] + [0] * 764
        self.table = pack(">768I", *self.values)
        self.compressed = b"\x80\xff\x00\x01\x00\x00\x81\x7f\xff" + b"\x80" * 764 + b"\0\0\0"
        self.suffix = bytes.fromhex("89abcdef")
        self.fill_start = 8 + len(self.compressed) + len(self.suffix)
        self.modules = [
            {"name": "header", "start": "0x400000", "end_exclusive": "0x400008"},
            {"name": "table", "start": "0x400008",
             "end_exclusive": hex(0x400008 + len(self.compressed)),
             "format": "mpw-compressed-dispatch"},
            {"name": "suffix", "start": hex(0x400008 + len(self.compressed)),
             "end_exclusive": hex(0x400000 + self.fill_start)},
        ]
        self.postlink = {"tool": "hiram", "rom_size": 128 * 1024,
                         "fill_start": hex(self.fill_start), "initials": "TST",
                         "date": "Oct 6"}
        self.stage_header(0x12345678)
        lines = ["rom_dispatch_offsets PROC EXPORT"]
        lines.extend("\tDC.L " + ",".join(map(str, self.values[i:i + 16]))
                     for i in range(0, len(self.values), 16))
        lines.extend(["\tENDP", "\tEND"])
        mpw.stage(self.build / "table.a", "\n".join(lines) + "\n")
        mpw.stage(self.build / "suffix.a", "rom_suffix PROC EXPORT\n\tDC.L $89abcdef\n\tENDP\n\tEND\n")

    def stage_header(self, value):
        mpw.stage(self.build / "header.a",
                  f"rom_header PROC EXPORT\n\tEXPORT BaseOfROM\nBaseOfROM EQU *\n"
                  f"\tDC.L 0,${value:08x}\n\tENDP\n\tEND\n")

    def run_build(self):
        return build_project(self.build, self.modules, self.postlink)

    def assert_image(self, value):
        prefix = pack(">II", 0, value)
        linked = mpw.resource_data(self.build / LINKED)
        self.assertEqual(linked[:self.fill_start], prefix + bytes(len(self.compressed)) + self.suffix)
        self.assertEqual(linked[self.fill_start:-28], self.table)
        unfinished = prefix + self.compressed + self.suffix
        self.assertEqual((self.build / UNFINISHED).read_bytes(), unfinished)
        image = (self.build / FINAL).read_bytes()
        self.assertEqual(len(image), self.postlink["rom_size"])
        self.assertEqual(image[4:self.fill_start], unfinished[4:])
        self.assertEqual(image[-6:], b"Oct 6\x05")
        self.assertEqual(image[self.fill_start:self.fill_start + 9], b"TSTTSTTST")
        checksum = sum(int.from_bytes(image[i:i + 2], "big")
                       for i in range(4, len(image), 2)) & 0xffffffff
        self.assertEqual(int.from_bytes(image[:4], "big"), checksum)

    def test_make_builds_the_image_and_reuses_unchanged_outputs(self):
        result = self.run_build()
        self.assert_image(0x12345678)
        self.assertEqual(result["dispatch_offset"], "0x8")
        tracked = ["header.o", "table.o", "hiram.c.o", "rombuild.c.o",
                   "hiram", "rombuild", FINAL, UNFINISHED, LINKED, MAP,
                   "header.a.lst", "table.a.lst"]
        before = {name: ((self.build / name).stat().st_mtime_ns, fingerprints(self.build / name))
                  for name in tracked}

        self.run_build()

        after = {name: ((self.build / name).stat().st_mtime_ns, fingerprints(self.build / name))
                 for name in tracked}
        self.assertEqual(after, before)
        log = (self.build / "mpw-make.stdout.log").read_text()
        self.assertNotRegex(log, r"(?m)^\s*(?:Asm|SC|Link)\s")
        self.assert_image(0x12345678)

    def test_missing_and_changed_listings_and_map_are_rebuilt(self):
        result = self.run_build()
        expected_symbols = {name: mpw.listing_symbols(self.build / name)
                            for name in ("header.a.lst", "table.a.lst")}
        expected_map = mpw.link_map(self.build / MAP)
        for name in (*expected_symbols, MAP):
            self.assertIn(name, result["outputs"])

        for name in ("header.a.lst", MAP):
            for change in ("delete", "corrupt"):
                with self.subTest(output=name, change=change):
                    path = self.build / name
                    if change == "delete":
                        path.unlink()
                    else:
                        original_stat = path.stat()
                        path.write_bytes(b"corrupted listing or map\n")
                        os.utime(path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

                    self.run_build()

                    for listing, symbols in expected_symbols.items():
                        self.assertEqual(mpw.listing_symbols(self.build / listing), symbols)
                    self.assertEqual(mpw.link_map(self.build / MAP), expected_map)
                    self.assert_image(0x12345678)

    def test_dispatch_relink_resolves_later_symbols_without_manifest_addresses(self):
        mpw.stage(self.build / "header.a", "rom_header PROC EXPORT\n"
                  "\tEXPORT BaseOfROM\n\tIMPORT Handler\nBaseOfROM EQU *\n"
                  "\tDC.L 0,Handler-BaseOfROM\n\tENDP\n\tEND\n")
        mpw.stage(self.build / "suffix.a", "rom_suffix PROC EXPORT\n"
                  "\tEXPORT Handler\nHandler EQU *\n\tDC.L $89abcdef\n\tENDP\n\tEND\n")
        mpw.stage(self.build / "table.a", "rom_dispatch_offsets PROC EXPORT\n"
                  "\tIMPORT Handler,BaseOfROM\n\tDC.L Handler-BaseOfROM\n"
                  "\tDCB.L 767,0\n\tENDP\n\tEND\n")
        for index, module in enumerate(self.modules):
            module["start"] = hex(0x400000 + index * 0x10000)
        self.postlink["fill_start"] = "0x8"

        result = self.run_build()

        symbols = mpw.link_map(self.build / MAP)
        output = (self.build / UNFINISHED).read_bytes()
        self.assertEqual(int.from_bytes(output[4:8], "big"), symbols["handler"])
        self.assertEqual(output[symbols["handler"]:], self.suffix)
        self.assertEqual(result["layout"]["dispatch_offset"], 8)
        table = output[8:symbols["handler"]]
        self.assertEqual(decode_dispatch_table(table, self.postlink["rom_size"])[0],
                         pack(">I", symbols["handler"]) + bytes(767 * 4))
        self.assertIn("relink required", (self.build / "mpw-make.stdout.log").read_text())

    def test_content_changes_corruption_and_assembly_failure_invalidate_outputs(self):
        self.run_build()
        source = self.build / "header.a"
        source_stat = source.stat()
        first_object = fingerprints(self.build / "header.o")
        self.stage_header(0x76543210)
        os.utime(source, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))

        self.run_build()

        self.assertNotEqual(fingerprints(self.build / "header.o"), first_object)
        self.assert_image(0x76543210)
        obj = self.build / "header.o"
        object_stat = obj.stat()
        valid_object = obj.read_bytes()
        obj.write_bytes(b"broken object")
        os.utime(obj, ns=(object_stat.st_atime_ns, object_stat.st_mtime_ns))

        self.run_build()

        self.assertEqual(obj.read_bytes(), valid_object)
        self.assert_image(0x76543210)
        mpw.stage(source, "Header PROC\n\tINVALID_OPCODE\n\tENDP\n\tEND\n")
        os.utime(source, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))

        with self.assertRaises(RuntimeError):
            self.run_build()

        for name in (FINAL, UNFINISHED, LINKED, STATE):
            with self.subTest(output=name):
                self.assertFalse((self.build / name).exists())

    def test_rez_resources_rebuild_after_input_changes_corruption_and_failure(self):
        source = self.build / "cursors.r"
        source.write_text('data \'CURS\' (2, sysheap, locked) { $"aa55" };\n')
        resource_start = self.fill_start
        resource = {"name": "cursors", "source": str(source), "format": "rez-data",
                    "start": hex(0x400000 + resource_start),
                    "end_exclusive": hex(0x400000 + resource_start + 10),
                    "block_flags": "0xc0", "first_master_pointer_offset": "0x80",
                    "resources": [{"type": "CURS", "id": 2, "label": "Curs2",
                                   "attributes": ["sysheap", "locked"]}]}
        self.modules.append(resource)
        self.fill_start += 10
        self.postlink["fill_start"] = hex(self.fill_start)
        original_suffix = self.suffix
        block_header = pack(">II", 0xc000000a, 0x80)
        self.suffix = original_suffix + block_header + bytes.fromhex("aa55")

        result = self.run_build()

        self.assert_image(0x12345678)
        symbols = mpw.link_map(self.build / MAP)
        for label, offset in (("curs2block", 0), ("curs2", 8), ("curs2end", 10)):
            self.assertEqual(symbols[label], resource_start + offset)
        self.assertIn("cursors.r", result["sources"])
        self.assertIn("cursors.layout", result["sources"])
        tracked = ["cursors.rsrc", "cursors.a", "cursors.o", "cursors.a.lst", FINAL]
        before = {name: ((self.build / name).stat().st_mtime_ns, fingerprints(self.build / name))
                  for name in tracked}

        self.run_build()

        self.assertEqual(before, {
            name: ((self.build / name).stat().st_mtime_ns, fingerprints(self.build / name))
            for name in tracked})
        self.assertNotRegex((self.build / "mpw-make.stdout.log").read_text(),
                            r'(?m)^\s*"?(?:Rez|rombuild|Asm|SC|Link)"?\s')

        source_stat = source.stat()
        mpw.stage(source, source.read_text().replace("aa55", "bb66"))
        os.utime(source, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
        self.suffix = original_suffix + block_header + bytes.fromhex("bb66")

        self.run_build()

        self.assert_image(0x12345678)
        self.assertNotEqual(fingerprints(self.build / "cursors.o"), before["cursors.o"][1])
        expected_assembly = (self.build / "cursors.a").read_bytes()
        expected_resource = fingerprints(self.build / "cursors.rsrc")
        for name in ("cursors.rsrc", "cursors.a"):
            with self.subTest(corrupted=name):
                path = self.build / name
                original_stat = path.stat()
                damaged = path / "..namedfork/rsrc" if name.endswith(".rsrc") else path
                damaged.write_bytes(b"corrupted resource output")
                os.utime(path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

                self.run_build()

                self.assert_image(0x12345678)
                self.assertEqual((self.build / "cursors.a").read_bytes(), expected_assembly)
                self.assertEqual(fingerprints(self.build / "cursors.rsrc"), expected_resource)

        source_stat = source.stat()
        mpw.stage(source, "invalid Rez source\n")
        os.utime(source, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
        with self.assertRaises(RuntimeError):
            self.run_build()
        for name in (FINAL, UNFINISHED, LINKED, STATE):
            with self.subTest(output=name):
                self.assertFalse((self.build / name).exists())


if __name__ == "__main__":
    unittest.main()
