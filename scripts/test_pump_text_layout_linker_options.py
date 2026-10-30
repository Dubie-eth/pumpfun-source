#!/usr/bin/env python3
"""Linker file options must not reach rust-lld outside the bound input set."""

from pathlib import Path
import tempfile
import unittest

import pump_text_layout

DEFAULT = Path(pump_text_layout.__file__).with_name("pump_text_layout_default.ld").read_text()
ORDERED = DEFAULT.replace(
    "  .text : { *(.text*) } :text",
    '  .text : {\n    *fixture.o(".text.fixture")\n    *(.text*)\n  } :text',
)


class LinkerOptionTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.sdk_script = self.root / "sdk.ld"
        self.sdk_script.write_text(DEFAULT)
        self.order = self.root / "ordered.ld"
        self.order.write_text(ORDERED)
        self.linker = self.root / "rust-lld"
        self.linker.write_bytes(b"linker")
        self.extra = self.root / "extra.ld"
        self.extra.write_text("ASSERT(0, \"unbound\");\n")

    def prepare(self, *extra):
        return pump_text_layout.prepare_link(
            [f"--script={self.sdk_script}", *extra, "-o", str(self.root / "out.so")],
            {"PUMP_TEXT_RECORD_DIR": str(self.root / "link"),
             "PUMP_TEXT_SCRIPT": str(self.order),
             "PUMP_TEXT_LINKER": str(self.linker)},
        )

    def test_single_dash_script_is_not_a_second_unbound_script(self):
        with self.assertRaisesRegex(AssertionError, "single-dash linker file option"):
            self.prepare(f"-script={self.extra}")

    def test_single_dash_file_options_are_not_unbound_inputs(self):
        for option in ("-script", "-version-script", "-just-symbols", "-dynamic-list",
                       "-retain-symbols-file", "-call-graph-ordering-file"):
            with self.subTest(option=option), self.assertRaisesRegex(
                AssertionError, "single-dash linker file option"
            ):
                pump_text_layout.declared_inputs([f"{option}={self.extra}"])

    def test_remapped_and_exported_list_files_are_not_unbound_inputs(self):
        for argv in (["--remap-inputs=bound.o=other.o"],
                     [f"--remap-inputs-file={self.extra}"],
                     [f"--export-dynamic-symbol-list={self.extra}"]):
            with self.subTest(argv=argv), self.assertRaisesRegex(
                AssertionError, "unsupported file option"
            ):
                pump_text_layout.declared_inputs(argv)

    def test_recipe_options_stay_admitted(self):
        arguments = ["-flavor", "gnu", "-shared", "-z", "notext", "-Bstatic", "--gc-sections",
                     "--strip-all", "--entry=entrypoint", "-L", str(self.root)]
        self.assertEqual(pump_text_layout.declared_inputs(arguments), {})
        command = self.prepare(*arguments)
        self.assertEqual(command[0], str(self.linker))
        self.assertIn(str(self.order), command[1])


if __name__ == "__main__":
    unittest.main()
