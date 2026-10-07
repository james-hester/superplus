import tempfile
from pathlib import Path
import unittest

import verify


class CompleteImageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="rom-image-test-")
        self.addCleanup(temporary.cleanup)
        self.build = Path(temporary.name)
        self.rom = bytes.fromhex("00000015 0001 0002 0003 0004 0005 0006")
        self.base = 0x400000
        self.output = self.build / "MacPlus-v3.rebuilt.bin"
        self.modules = []
        for name, lo, hi in (("first", 0, 8), ("second", 8, 16)):
            data = self.rom[lo:hi]
            (self.build / (name + ".bin")).write_bytes(data)
            self.modules.append({"name": name, "start": hex(self.base + lo),
                                 "end_exclusive": hex(self.base + hi), "sha256": verify.sha256(data)})

    def test_complete_image_uses_binary_order_and_checks_checksum(self):
        result = verify.build_image(self.modules[::-1], self.rom, self.base, self.build)
        self.assertEqual(self.output.read_bytes(), self.rom)
        self.assertEqual(result["checksum"], "0x15")
        self.assertEqual(result["sha256"], verify.sha256(self.rom))
        self.assertTrue(result["complete"])

    def test_gap_removes_stale_image_without_filling_from_reference(self):
        self.output.write_bytes(self.rom)
        result = verify.build_image(self.modules[:1], self.rom, self.base, self.build)
        self.assertFalse(result["complete"])
        self.assertEqual(result["gaps"], [{"start": "0x400008", "end_exclusive": "0x400010", "bytes": 8}])
        self.assertFalse(self.output.exists())

    def test_changed_binary_is_rejected_before_image_publication(self):
        part = self.build / "second.bin"
        part.write_bytes(b"\0" * 8)
        with self.assertRaisesRegex(ValueError, "changed after verification"):
            verify.build_image(self.modules, self.rom, self.base, self.build)
        self.modules[1]["sha256"] = verify.sha256(part.read_bytes())
        with self.assertRaisesRegex(ValueError, "differs from the reference"):
            verify.build_image(self.modules, self.rom, self.base, self.build)
        self.assertFalse(self.output.exists())

    def test_overlapping_spans_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "overlap"):
            verify.build_image(self.modules + self.modules[:1], self.rom, self.base, self.build)

    def test_matching_bytes_still_require_the_rom_checksum(self):
        bad_rom = b"\0\0\0\0" + self.rom[4:]
        (self.build / "first.bin").write_bytes(bad_rom[:8])
        self.modules[0]["sha256"] = verify.sha256(bad_rom[:8])
        with self.assertRaisesRegex(ValueError, "checksum"):
            verify.build_image(self.modules, bad_rom, self.base, self.build)
        self.assertFalse(self.output.exists())


class HiramImageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="rom-postlink-test-")
        self.addCleanup(temporary.cleanup)
        self.build = Path(temporary.name)
        self.base = 0x400000
        self.settings = {"tool": "hiram", "rom_size": 131072, "fill_start": "0x1ffd0",
                         "initials": "HB JTC SC DLD PWD KWK LAK SEL B", "date": "Wed, Nov 6, 1985"}
        self.prefix = bytes(4) + bytes((i * 17 + 3) % 256 for i in range(4, 0x1ffd0))
        date = self.settings["date"].encode("ascii")
        image = self.prefix + self.settings["initials"].encode("ascii") + date + bytes([len(date)])
        checksum = sum(int.from_bytes(image[i:i + 2], "big") for i in range(4, len(image), 2))
        self.rom = (checksum & 0xffffffff).to_bytes(4, "big") + image[4:]
        self.modules = []
        for name, start, end in (("header", 0, 64), ("middle", 64, 128), ("body", 128, 0x1ffd0)):
            part = self.prefix[start:end]
            (self.build / (name + ".bin")).write_bytes(part)
            self.modules.append({"name": name, "start": hex(self.base + start),
                                 "end_exclusive": hex(self.base + end), "sha256": verify.sha256(part)})
        self.modules[0]["postlink_checksum"] = True
        (self.build / "MacPlus-v3.unfinished.bin").write_bytes(self.prefix)
        (self.build / "MacPlus-v3.hiram.bin").write_bytes(self.rom)

    def test_verifies_hiram_output_and_declared_spans(self):
        result = verify.build_image(self.modules, self.rom, self.base, self.build, self.settings)
        self.assertEqual((self.build / "MacPlus-v3.rebuilt.bin").read_bytes(), self.rom)
        self.assertEqual((self.build / "MacPlus-v3.unfinished.bin").read_bytes(), self.prefix)
        generated = result["postlink"]["generated_spans"]
        self.assertEqual([(span["offset"], span["bytes"]) for span in generated],
                         [("0x0", 4), ("0x1ffd0", 48)])
        self.assertEqual(result["postlink"]["output_sha256"], verify.sha256(self.rom))

    def test_hiram_cannot_fill_missing_assembled_bytes(self):
        for modules in (self.modules[:1], self.modules[1:], [self.modules[0], self.modules[2]]):
            with self.subTest(modules=modules):
                result = verify.build_image(modules, self.rom, self.base, self.build, self.settings)
                self.assertFalse(result["complete"])
                self.assertFalse((self.build / "MacPlus-v3.rebuilt.bin").exists())

    def test_assembled_data_cannot_overlap_hiram_span(self):
        body = self.modules[2]
        payload = self.prefix[128:] + b"XX"
        (self.build / "body.bin").write_bytes(payload)
        body.update(end_exclusive=hex(self.base + 0x1ffd2), sha256=verify.sha256(payload))
        with self.assertRaisesRegex(ValueError, "overlaps the Hiram fill span"):
            verify.build_image(self.modules, self.rom, self.base, self.build, self.settings)

    def test_changed_metadata_fails_final_byte_comparison(self):
        changed = bytearray(self.rom)
        changed[-3] ^= 1
        checksum = sum(int.from_bytes(changed[i:i + 2], "big") for i in range(4, len(changed), 2))
        changed[:4] = (checksum & 0xffffffff).to_bytes(4, "big")
        (self.build / "MacPlus-v3.hiram.bin").write_bytes(changed)
        with self.assertRaisesRegex(ValueError, "differs from the reference"):
            verify.build_image(self.modules, self.rom, self.base, self.build, self.settings)
        self.assertFalse((self.build / "MacPlus-v3.rebuilt.bin").exists())

    def test_checksum_placeholder_requires_hiram_and_zero_bytes(self):
        with self.assertRaisesRegex(ValueError, "requires Hiram"):
            verify.build_image(self.modules, self.prefix, self.base, self.build)
        payload = b"BAD!" + self.prefix[4:64]
        (self.build / "header.bin").write_bytes(payload)
        self.modules[0]["sha256"] = verify.sha256(payload)
        with self.assertRaisesRegex(ValueError, "zero checksum placeholder"):
            verify.build_image(self.modules, self.rom, self.base, self.build, self.settings)

    def test_hiram_may_not_change_other_header_fields(self):
        changed = bytearray(self.rom)
        changed[0x30] ^= 1
        (self.build / "MacPlus-v3.hiram.bin").write_bytes(changed)
        with self.assertRaisesRegex(ValueError, "outside the checksum"):
            verify.build_image(self.modules, self.rom, self.base, self.build, self.settings)

    def test_unfinished_image_must_match_verified_modules(self):
        changed = bytearray(self.prefix)
        changed[0x30] ^= 1
        (self.build / "MacPlus-v3.unfinished.bin").write_bytes(changed)
        with self.assertRaisesRegex(ValueError, "ROMBuild changed"):
            verify.build_image(self.modules, self.rom, self.base, self.build, self.settings)


if __name__ == "__main__":
    unittest.main()
