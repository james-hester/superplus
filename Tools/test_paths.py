import hashlib
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

import paths


class SourcePathTests(unittest.TestCase):
    def test_local_and_legacy_paths_resolve_to_project(self):
        expected = paths.HERE / "Source/OS/StartMgr/StartInit.a"
        self.assertEqual(paths.source_path("Source/OS/StartMgr/StartInit.a"), expected)
        self.assertEqual(paths.source_path("Reconstruction/Source/OS/StartMgr/StartInit.a"), expected)

    def test_absolute_paths_are_preserved(self):
        absolute = Path("/tmp/source.a")
        self.assertEqual(paths.source_path(absolute), absolute)
        self.assertEqual(paths.historical_path(absolute), absolute)

    def test_historical_root_accepts_environment_override(self):
        with tempfile.TemporaryDirectory(prefix="historical-root-test-") as directory:
            with patch.dict(os.environ, {"SUPER_MARIO_ROOT": directory}):
                module = runpy.run_path(paths.__file__)
            self.assertEqual(module["historical_path"]("OS/HFS/VSM.a"),
                             Path(directory).resolve() / "OS/HFS/VSM.a")


class InventoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="inventory-path-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write_source(self, name, data, baseline=None):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return {"path": name, "sha256": hashlib.sha256(data if baseline is None else baseline).hexdigest()}

    def header_source(self, body_line):
        header = [b";\n", b"; File: source.a\n", b";\n",
                  b"; Contains: volume routines\n", b"; and helpers.\n"]
        header.extend([b"; history\n"] * (body_line - 1 - len(header)))
        body = [b"\n", b";________________________________________\n", b"Start RTS\n"]
        return header + body, b"".join(header[3:5] + body)

    def test_exact_bytes_and_hashes_are_retained(self):
        data = b"Start RTS\n"
        item = self.write_source("Original.a", data)
        self.assertEqual(paths.inventory_bytes(item, root=self.root), data)
        self.assertEqual(paths.inventory_record(item, root=self.root), {
            "path": "Original.a", "recorded_sha256": item["sha256"],
            "actual_sha256": item["sha256"], "verification": "exact",
        })

    def test_known_header_projections_preserve_baseline_bytes(self):
        for name, body_line in (("OS/HFS/TFSVOL.a", 193), ("OS/HFS/VSM.a", 50)):
            with self.subTest(name=name):
                lines, baseline = self.header_source(body_line)
                data = b"".join(lines)
                item = self.write_source(name, data, baseline)
                self.assertEqual(paths.inventory_bytes(item, root=self.root), baseline)
                record = paths.inventory_record(item, root=self.root)
                self.assertEqual(record["verification"], "header_projection")
                self.assertEqual(record["actual_sha256"], hashlib.sha256(data).hexdigest())
                self.assertNotEqual(record["actual_sha256"], record["recorded_sha256"])

    def test_projection_does_not_apply_to_other_files(self):
        lines, baseline = self.header_source(50)
        item = self.write_source("OS/HFS/Other.a", b"".join(lines), baseline)
        with self.assertRaisesRegex(ValueError, "differs from the recorded inventory"):
            paths.inventory_bytes(item, root=self.root)

    def test_projection_rejects_instructions_in_omitted_header(self):
        for line in (0, 2, 5, 48):
            with self.subTest(line=line):
                lines, baseline = self.header_source(50)
                lines[line] = b"Unexpected NOP\n"
                item = self.write_source("OS/HFS/VSM.a", b"".join(lines), baseline)
                with self.assertRaisesRegex(ValueError, "differs from the recorded inventory"):
                    paths.inventory_bytes(item, root=self.root)

    def test_projection_rejects_changed_body(self):
        lines, baseline = self.header_source(50)
        lines[-1] = b"Start NOP\n"
        item = self.write_source("OS/HFS/VSM.a", b"".join(lines), baseline)
        with self.assertRaisesRegex(ValueError, "differs from the recorded inventory"):
            paths.inventory_bytes(item, root=self.root)

    def test_projection_rejects_malformed_header_and_boundary(self):
        for line, replacement in ((3, b"; No description\n"), (4, b"Unexpected NOP\n"),
                                  (49, b"; Not a blank line\n"), (50, b"; No divider\n")):
            with self.subTest(line=line):
                lines, _ = self.header_source(50)
                lines[line] = replacement
                baseline = b"".join(lines[3:5] + lines[49:])
                item = self.write_source("OS/HFS/VSM.a", b"".join(lines), baseline)
                with self.assertRaisesRegex(ValueError, "differs from the recorded inventory"):
                    paths.inventory_bytes(item, root=self.root)

    def test_projection_rejects_truncated_source(self):
        item = self.write_source("OS/HFS/VSM.a", b"; truncated\n", b"Start RTS\n")
        with self.assertRaisesRegex(ValueError, "differs from the recorded inventory"):
            paths.inventory_bytes(item, root=self.root)


if __name__ == "__main__":
    unittest.main()
