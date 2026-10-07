from pathlib import Path
import tempfile
import unittest

import mpw


class NativeListingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.runner = mpw.executable()
        except FileNotFoundError as error:
            raise unittest.SkipTest(str(error))

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="macplus-listing-")
        self.directory = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def link(self, sources):
        objects = []
        for name, source in sources:
            mpw.stage(self.directory / (name + ".a"), source)
            mpw.run(self.runner, "Asm", ["-sym", "on,nolines", "-wb", "-l", "-o",
                    name + ".o", name + ".a"], self.directory)
            objects.append(name + ".o")
        listing, diagnostics = mpw.run(self.runner, "Link", ["-t", "ZROM", "-rt", "ROM =0",
                                        "-la", "-o", "linked.rom", *objects], self.directory)
        self.assertEqual(diagnostics.strip(), "")
        (self.directory / "linked.map").write_text(listing)
        return mpw.link_map(self.directory / "linked.map")

    def test_native_procedures_and_labels_use_linked_offsets(self):
        locations = self.link([("scopes", """        MACHINE MC68000
Marker PROC EXPORT
        ENDP
First PROC EXPORT
Code NOP
@loop DC.W 3
Alias EQU *
Second FUNC EXPORT
Code MOVEQ #1,D0
@loop NOP
lo16 EQU *+2
Tail DC.L $12345678
Last
        ENDF
        END
""")])
        symbols, size = mpw.listing_symbols(self.directory / "scopes.a.lst", locations)
        self.assertEqual(size, 12)
        self.assertEqual(symbols["marker"], 0)
        self.assertEqual(symbols["first"], 0)
        self.assertEqual(symbols["first__code"], 0)
        self.assertEqual(symbols["alias"], 4)
        self.assertEqual(symbols["second"], 4)
        self.assertEqual(symbols["second__code"], 4)
        self.assertEqual(symbols["code__local_loop"], 6)
        self.assertEqual(symbols["second__lo16"], 10)
        self.assertEqual(symbols["last"], 12)
        self.assertEqual(len(mpw.resource_data(self.directory / "linked.rom")), size)

    def test_private_procedure_names_can_repeat_in_other_objects(self):
        locations = self.link([
            ("first", """Prefix PROC EXPORT
        NOP
Common PROC
Here RTS
        END
"""),
            ("second", """SecondMarker PROC EXPORT
        ENDP
Common PROC
Here DC.L $12345678
        END
""")])
        first, first_size = mpw.listing_symbols(self.directory / "first.a.lst", locations)
        second, second_size = mpw.listing_symbols(self.directory / "second.a.lst", locations, 4)
        self.assertEqual(first["common"], 2)
        self.assertEqual(first["here"], 2)
        self.assertEqual(first_size, 4)
        self.assertEqual(second["common"], 0)
        self.assertEqual(second["here"], 0)
        self.assertEqual(second_size, 4)

    def test_macro_and_conditional_listings_record_emitted_labels(self):
        locations = self.link([("conditional", """        MACRO
        Padding
        DC.W $1234
        ENDM
Block PROC EXPORT
Before Padding
        IF 0 THEN
Absent DC.W $FFFF
        ELSE
Present DC.W 7
        ENDIF
After RTS
        END
""")])
        symbols, size = mpw.listing_symbols(self.directory / "conditional.a.lst", locations)
        self.assertNotIn("absent", symbols)
        self.assertEqual(symbols["before"], 0)
        self.assertEqual(symbols["present"], 2)
        self.assertEqual(symbols["after"], 4)
        self.assertEqual(size, 6)

    def test_colon_labels_include_comments_without_separating_spaces(self):
        locations = self.link([("colons", """Block PROC EXPORT
Start: NOP
Bare:
Joined:;MPW accepts the comment directly after the colon.
@loop: RTS
        END
""")])
        symbols, size = mpw.listing_symbols(self.directory / "colons.a.lst", locations)
        self.assertEqual(symbols["start"], 0)
        self.assertEqual(symbols["bare"], 2)
        self.assertEqual(symbols["joined"], 2)
        self.assertEqual(symbols["joined__local_loop"], 2)
        self.assertEqual(size, 4)

    def test_explicit_procedure_ends_work_without_a_link_map(self):
        self.link([("explicit", """First PROC EXPORT
Start EQU *
        DC.W $1234
        ENDP
Second PROC EXPORT
Next EQU *
        DC.L $56789ABC
        ENDP
        END
""")])
        symbols, size = mpw.listing_symbols(self.directory / "explicit.a.lst")
        self.assertEqual(symbols["start"], 0)
        self.assertEqual(symbols["next"], 2)
        self.assertEqual(size, 6)


if __name__ == "__main__":
    unittest.main()
