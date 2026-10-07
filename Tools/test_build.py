import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from stage import ROOT, stage, write_text


class NativeBuildTests(unittest.TestCase):
    def test_build_renames_changes_and_errors(self):
        with tempfile.TemporaryDirectory(prefix="macplus build ") as directory:
            build = Path(directory)
            stage(build)
            source = build / "Source/ROMTail.a"
            original = source.read_bytes().decode("mac_roman").replace("\r", "\n")
            fixture = "BuildTest PROC\nPrivateLabel EQU *\n\tENDP\n"
            write_text(source, fixture + original)

            def make():
                return subprocess.run(
                    ["make", "-f", str(ROOT / "Makefile"), "native", "BUILD=" + str(build)],
                    cwd=build, capture_output=True, encoding="mac_roman")

            def verify():
                return subprocess.run(
                    ["shasum", "-a", "256", "-c", str(ROOT / "ROM/MacPlus-v3.sha256")],
                    cwd=build, capture_output=True, text=True)

            def assert_build():
                result = make()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result

            assert_build()
            self.assertEqual(verify().returncode, 0)
            output = build / "MacPlus-v3.rebuilt.bin"
            first_time = output.stat().st_mtime_ns
            assert_build()
            self.assertEqual(output.stat().st_mtime_ns, first_time)

            fixture = fixture.replace("PrivateLabel", "RenamedLabel")
            write_text(source, fixture + original)
            output.unlink()
            assert_build()
            self.assertEqual(verify().returncode, 0)

            fixture = fixture.replace("EQU *", "NOP")
            write_text(source, fixture + original)
            output.unlink()
            assert_build()
            self.assertNotEqual(verify().returncode, 0)

            write_text(source, "\tInvalidOpcode\n" + original)
            output.unlink()
            result = make()
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(output.exists())

            makefile = build / "MPW/ROM.make"
            text = makefile.read_bytes().decode("mac_roman").replace("\r", "\n")
            write_text(makefile, text.replace("MacPlus-v3.rebuilt.bin ƒ",
                                             "MacPlus-v3.rebuilt.bin ƒ MissingBuildInput"))
            result = make()
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)


class StagingTests(unittest.TestCase):
    def test_conversion_updates_and_deleted_includes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            source = root / "Source/Includes/Values.a"
            source.parent.mkdir(parents=True)
            source.write_text("; © Apple\nValue EQU 1\n")
            build = root / "Build"
            stage(build, root)
            copy = build / "Source/Includes/Values.a"
            self.assertEqual(copy.read_bytes(), b"; \xa9 Apple\rValue EQU 1\r")
            timestamp = (build / "SourceStamp").stat().st_mtime_ns
            stage(build, root)
            self.assertEqual((build / "SourceStamp").stat().st_mtime_ns, timestamp)
            old_stat = source.stat()
            source.write_text("Value EQU 2\n")
            os.utime(source, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
            stage(build, root)
            self.assertEqual(copy.read_bytes(), b"Value EQU 2\r")
            source.unlink()
            stage(build, root)
            self.assertFalse(copy.exists())

    def test_rejects_staging_over_source_tree(self):
        with self.assertRaises(ValueError):
            stage(ROOT)


if __name__ == "__main__":
    unittest.main()
