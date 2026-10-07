import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import index_sources


class SourceInventoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="source-index-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.reconstruction = self.root / "Reconstruction"
        self.evidence = self.reconstruction / "Evidence"
        self.evidence.mkdir(parents=True)
        self.original = self.root / "Original.a"
        self.original.write_text("Start RTS\n")
        (self.evidence / "ghidra-symbols.tsv").write_text(
            "address\tname\ttype\tsource\n00400000\tStart\tLabel\tUSER_DEFINED\n"
        )
        self.inventory = self.evidence / "source-inventory.json"
        self.candidates = self.evidence / "source-candidates.tsv"

    def run_index(self):
        with patch.object(index_sources, "ROOT", self.root), \
                patch.object(index_sources, "RECONSTRUCTION", self.reconstruction), \
                patch("sys.argv", ["index_sources.py"]), \
                contextlib.redirect_stdout(io.StringIO()):
            index_sources.main()

    def record_inventory(self):
        self.inventory.write_text(json.dumps([
            {"path": "Original.a", "sha256": hashlib.sha256(self.original.read_bytes()).hexdigest()}
        ], indent=2) + "\n")

    def test_new_reference_files_do_not_expand_existing_inventory(self):
        self.record_inventory()
        baseline = self.inventory.read_bytes()
        self.run_index()
        candidates = self.candidates.read_bytes()
        added = self.root / "QuickDraw Source"
        added.mkdir()
        (added / "Extra.a").write_text("Start NOP\n")
        self.run_index()
        self.assertEqual(self.inventory.read_bytes(), baseline)
        self.assertEqual(self.candidates.read_bytes(), candidates)

    def test_changed_original_fails_before_candidate_output_changes(self):
        self.record_inventory()
        baseline = self.inventory.read_bytes()
        self.run_index()
        candidates = self.candidates.read_bytes()
        self.original.write_text("Changed RTS\n")
        with self.assertRaisesRegex(ValueError, "differs from the recorded inventory"):
            self.run_index()
        self.assertEqual(self.inventory.read_bytes(), baseline)
        self.assertEqual(self.candidates.read_bytes(), candidates)

    def test_initial_discovery_records_original_assembly_only(self):
        (self.root / "Extra.a").write_text("Other RTS\n")
        (self.reconstruction / "Generated.a").write_text("Start NOP\n")
        self.run_index()
        entries = json.loads(self.inventory.read_text())
        self.assertEqual([item["path"] for item in entries], ["Extra.a", "Original.a"])
        self.assertIn("Original.a", self.candidates.read_text())
        self.assertNotIn("Generated.a", self.candidates.read_text())


if __name__ == "__main__":
    unittest.main()
