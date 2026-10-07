from pathlib import Path
import subprocess
import tempfile
import unittest

from mpw import build_tool


class HiramTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compiler_directory = tempfile.TemporaryDirectory(prefix="hiram-compiler-")
        cls.addClassCleanup(cls.compiler_directory.cleanup)
        tool = build_tool("hiram", cls.compiler_directory.name)
        cls.hiram = tool["executable"]
        cls.runner = tool["runner"]

    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="hiram-test-")
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)

    def finish(self, payload, *, size=1, initials="AB_CD", date="test date",
               fill_start=None, omit=()):
        source = self.directory / "prefix.bin"
        output = self.directory / "image.bin"
        source.write_bytes(payload)
        options = {"-s": str(size), "-i": initials, "-fd": date,
                   "--fill-start": hex(len(payload) if fill_start is None else fill_start)}
        args = [*self.runner, str(self.hiram)]
        for option, value in options.items():
            if option not in omit:
                args.extend([option, value])
        result = subprocess.run([*args, str(source), str(output)], capture_output=True,
                                text=True)
        return result, output

    def assert_checksum(self, image):
        total = sum(int.from_bytes(image[i:i + 2], "big")
                    for i in range(4, len(image), 2)) & 0xffffffff
        self.assertEqual(int.from_bytes(image[:4], "big"), total)

    def test_preserves_code_and_uses_unsigned_big_endian_checksum(self):
        payload = bytes([0x81, 0xff, 0x80, 0x01]) * 249
        result, output = self.finish(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        image = output.read_bytes()
        self.assertEqual(len(image), 1024)
        self.assertEqual(image[4:len(payload)], payload[4:])
        self.assertEqual(image[0x30:0x44], payload[0x30:0x44])
        self.assert_checksum(image)
        changed_header = b"\x00\x00\x00\x00" + payload[4:]
        result, output = self.finish(changed_header)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_bytes(), image)

    def test_initials_repeat_and_date_ends_with_its_length(self):
        payload = b"\x00" * 1001
        result, output = self.finish(payload, date="Nov 6")
        self.assertEqual(result.returncode, 0, result.stderr)
        image = output.read_bytes()
        self.assertEqual(image[1001:-6], b"AB CDAB CDAB CDAB")
        self.assertEqual(image[-6:], b"Nov 6\x05")
        self.assert_checksum(image)
        result, output = self.finish(payload, initials="AB CD", date="Nov 6")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_bytes(), image)

    def test_macplus_metadata_matches_recorded_fields(self):
        result, output = self.finish(
            bytes(0x1ffd0), size=128,
            initials="HB_JTC_SC_DLD_PWD_KWK_LAK_SEL_B", date="Wed, Nov 6, 1985")
        self.assertEqual(result.returncode, 0, result.stderr)
        image = output.read_bytes()
        self.assertEqual(image[0x1ffd0:0x1ffef], b"HB JTC SC DLD PWD KWK LAK SEL B")
        self.assertEqual(image[0x1ffef:], b"Wed, Nov 6, 1985\x10")
        self.assert_checksum(image)

    def test_checksum_wraps_at_32_bits_and_includes_last_word(self):
        payload = b"\xff" * (256 * 1024 - 2)
        result, output = self.finish(payload, size=256, initials="Z", date="")
        self.assertEqual(result.returncode, 0, result.stderr)
        image = output.read_bytes()
        full_sum = ((len(payload) - 4) // 2) * 65535 + 0x5a00
        self.assertGreater(full_sum, 0xffffffff)
        self.assertEqual(int.from_bytes(image[:4], "big"), full_sum & 0xffffffff)
        self.assertEqual(image[-2:], b"Z\x00")

    def test_date_can_occupy_all_remaining_space(self):
        result, output = self.finish(bytes(1008), date="D" * 15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_bytes()[1008:], b"D" * 15 + b"\x0f")

    def test_invalid_metadata_and_input_lengths_are_rejected(self):
        cases = [
            ({"initials": ""}, "initials must not be empty"),
            ({"date": "D" * 256}, "date exceeds"),
            ({"date": "D" * 24}, "date overlaps"),
            ({"fill_start": 999}, "input length"),
            ({"fill_start": 1001}, "input length"),
            ({"fill_start": 3}, "fill start is outside"),
            ({"fill_start": 1025}, "fill start is outside"),
            ({"omit": ("-fd",)}, "are required"),
            ({"initials": "A\nB"}, "printable ASCII"),
            ({"date": "café"}, "printable ASCII"),
        ]
        for options, message in cases:
            with self.subTest(options=options):
                result, output = self.finish(bytes(1000), **options)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertFalse(output.exists())

    def test_invalid_numbers_are_rejected(self):
        for size in ("-1", "+1", " 1", "\t-1", "garbage", "0", "1junk",
                     "18446744073709551616"):
            with self.subTest(size=size):
                result, output = self.finish(bytes(1000), size=size)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
