#!/usr/bin/env python3
"""The aggregate Pump corpus must publish its report on Windows.

Sibling of merged #2908 (diagnostic auditor), open #2937
(strict-ordered-log receipts) and #2949 (data-order certificates):
those scripts staged a complete receipt and then unconditionally
hard-linked it to the output, and in a Windows sandbox os.link fails
with WinError 5, so no receipt was retained. This script published its
44-suite report the same way — an unconditional os.link in main() —
so on Windows every run failed at the final step even when all 10,468
cases passed, leaving only the retained staging copy for manual
recovery instead of the requested output.

Windows itself is not available here, so the Windows host is simulated
for the publish helper by patching os.name to 'nt' and making os.link
raise the sandbox error; the POSIX path is exercised for real.

The module cannot be imported on this host (it pulls in the solders
dependency through pump_amm_reusable_harness, which is not installed
here), so the helper is exercised by extracting its real definition
from the module source and the main() wiring is checked by AST — the
same approach the strict-ordered-logs Windows test uses for its
main() wiring. The helper tests fail on base (no publish_file
definition) and pass with the fix; the wiring test fails on base
(main() calls os.link directly).
"""
import ast
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent
SOURCE = (SCRIPTS / "pump_validate_all.py").read_text(encoding="utf-8")


def load_publish_file():
    """Exec the module's real publish_file definition in isolation."""
    tree = ast.parse(SOURCE)
    function = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "publish_file")
    namespace = {"os": os}
    exec(compile(ast.Module(body=[function], type_ignores=[]),
                 str(SCRIPTS / "pump_validate_all.py"), "exec"),
         namespace)
    return namespace["publish_file"]


class ValidateAllWindowsPublishTests(unittest.TestCase):
    def test_publish_file_uses_rename_on_windows(self):
        publish_file = load_publish_file()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staged = root / ".report.json.staged"
            staged.write_text('{"cases": 0}\n', encoding="utf-8")
            output = root / "report.json"
            with mock.patch.object(os, "name", "nt"), \
                    mock.patch.object(os, "link",
                                      side_effect=OSError("WinError 5")) as link:
                publish_file(staged, output)
            link.assert_not_called()
            self.assertEqual(output.read_text(encoding="utf-8"),
                             '{"cases": 0}\n')
            self.assertFalse(staged.exists())

    def test_publish_file_uses_link_on_posix(self):
        publish_file = load_publish_file()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staged = root / ".report.json.staged"
            staged.write_text('{"cases": 0}\n', encoding="utf-8")
            output = root / "report.json"
            publish_file(staged, output)
            self.assertEqual(output.read_text(encoding="utf-8"),
                             '{"cases": 0}\n')
            self.assertTrue(staged.exists())

    def test_main_publishes_through_publish_file(self):
        tree = ast.parse(SOURCE)
        function = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "main")
        calls = []
        for node in ast.walk(function):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    calls.append(node.func.attr)
                elif isinstance(node.func, ast.Name):
                    calls.append(node.func.id)
        self.assertIn("publish_file", calls)
        self.assertNotIn("link", calls)


if __name__ == "__main__":
    unittest.main()
