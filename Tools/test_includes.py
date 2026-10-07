from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from verify import expand_includes


class IncludeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def write(self, name, content):
        path = self.root / name
        path.write_text(content)
        return path

    def test_nested_includes_preserve_order_and_record_dependencies(self):
        source = self.write('Module.a', "; INCLUDE 'Missing.a'\n\tINCLUDE 'Types.a' ; fields\n\tRTS\n")
        self.write('Types.a', "V EQU 0\n\tinclude 'Modes.a'\nH EQU 2\n")
        self.write('Modes.a', 'FRAME EQU 0\n')
        dependencies = {}
        result = expand_includes(source, dependencies)
        self.assertEqual([line for line in result.splitlines() if line],
                         ["; INCLUDE 'Missing.a'", 'V EQU 0', 'FRAME EQU 0', 'H EQU 2', '\tRTS'])
        self.assertEqual({Path(path).name for path in dependencies}, {'Module.a', 'Types.a', 'Modes.a'})

    def test_changed_include_changes_dependency_hash(self):
        source = self.write('Module.a', "\tINCLUDE 'Types.a'\n")
        included = self.write('Types.a', 'V EQU 0\n')
        before, after = {}, {}
        expand_includes(source, before)
        included.write_text('V EQU 1\n')
        expand_includes(source, after)
        self.assertNotEqual(before[str(included)], after[str(included)])
        self.assertEqual(before[str(source)], after[str(source)])

    def test_cycle_fails(self):
        source = self.write('Module.a', "\tINCLUDE 'Types.a'\n")
        self.write('Types.a', "\tINCLUDE 'Module.a'\n")
        with self.assertRaisesRegex(ValueError, 'Include cycle'):
            expand_includes(source, {})

    def test_missing_file_fails(self):
        source = self.write('Module.a', "\tINCLUDE 'Missing.a'\n")
        with self.assertRaises(FileNotFoundError):
            expand_includes(source, {})

    def test_unsupported_syntax_fails(self):
        source = self.write('Module.a', '\tINCLUDE Types.a\n')
        with self.assertRaisesRegex(ValueError, 'unsupported INCLUDE syntax'):
            expand_includes(source, {})

    def test_parent_directory_include_fails(self):
        source = self.write('Module.a', "\tINCLUDE '../Types.a'\n")
        with self.assertRaisesRegex(ValueError, 'same directory'):
            expand_includes(source, {})

    def test_shared_include_search_preserves_local_precedence_and_hashes(self):
        shared = self.root / "shared"
        shared.mkdir()
        source = self.root / "Module.a"
        source.write_text("\tINCLUDE 'Types.a'\n")
        types = shared / "Types.a"
        types.write_text("\tINCLUDE 'Nested.a'\nVALUE EQU 1\n")
        nested = shared / "Nested.a"
        nested.write_text("OTHER EQU 2\n")
        dependencies = {}
        expanded = expand_includes(source, dependencies, include_dirs=(shared,))
        self.assertIn("OTHER EQU 2", expanded)
        self.assertEqual(dependencies[str(nested.resolve())], sha256(nested.read_bytes()).hexdigest())
        (self.root / "Types.a").write_text("VALUE EQU 3\n")
        local_dependencies = {}
        expanded = expand_includes(source, local_dependencies, include_dirs=(shared,))
        self.assertIn("VALUE EQU 3", expanded)
        self.assertNotIn(str(types.resolve()), local_dependencies)
        (self.root / "Types.a").unlink()
        nested.write_text("\tINCLUDE 'Types.a'\n")
        with self.assertRaisesRegex(ValueError, "Include cycle"):
            expand_includes(source, {}, include_dirs=(shared,))


if __name__ == '__main__':
    unittest.main()
