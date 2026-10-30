#!/usr/bin/env python3
"""Strict-log audit receipts must publish on Windows without hard links.

Sibling of merged #2908, which fixed the same defect in the diagnostic
auditor: that script staged a complete receipt and then unconditionally
hard-linked it to the output, and in a Windows sandbox os.link fails
with WinError 5, so no receipt was retained. This script published its
audit receipt the same way — an unconditional os.link in main().

Windows itself is not available here, so the Windows host is simulated
for the publish helper by patching os.name to 'nt' and making os.link
raise the sandbox error; the POSIX path is exercised for real. Patching
os.name for a whole main() run is not viable on this host (pathlib
picks its flavour from os.name), so the main() wiring is checked by
AST instead: main() must publish through publish_file, not os.link.
The helper tests fail on base (no publish_file) and pass with the
fix; the wiring test fails on base (main() calls os.link directly).
"""
import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pump_strict_ordered_logs as gate  # noqa: E402


class StrictOrderedLogsWindowsPublishTests(unittest.TestCase):
    def test_publish_file_uses_rename_on_windows(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staged = root / ".audit.json.staged"
            staged.write_text("receipt", encoding="utf-8")
            output = root / "audit.json"
            with mock.patch.object(gate.os, "name", "nt"), \
                    mock.patch.object(gate.os, "link",
                                      side_effect=OSError("WinError 5")) as link:
                consumed = gate.publish_file(staged, output)
            self.assertTrue(consumed)
            link.assert_not_called()
            self.assertEqual(output.read_text(encoding="utf-8"), "receipt")
            self.assertFalse(staged.exists())

    def test_publish_file_uses_link_on_posix(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staged = root / ".audit.json.staged"
            staged.write_text("receipt", encoding="utf-8")
            output = root / "audit.json"
            with mock.patch.object(gate.os, "name", "posix"):
                consumed = gate.publish_file(staged, output)
            self.assertFalse(consumed)
            self.assertEqual(output.read_text(encoding="utf-8"), "receipt")
            self.assertTrue(gate.os.path.samefile(staged, output))
            staged.unlink(missing_ok=True)

    def test_main_publishes_through_publish_file(self):
        tree = ast.parse(
            (Path(__file__).resolve().parent
             / "pump_strict_ordered_logs.py").read_text(encoding="utf-8"))
        main = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "main")
        calls = [
            node for node in ast.walk(main)
            if isinstance(node, ast.Call)
        ]
        publishes = any(
            isinstance(call.func, ast.Name) and call.func.id == "publish_file"
            for call in calls
        )
        self.assertTrue(publishes, "main() does not publish through publish_file")
        links = any(
            isinstance(call.func, ast.Attribute) and call.func.attr == "link"
            for call in calls
        )
        self.assertFalse(links, "main() still calls os.link directly")


if __name__ == "__main__":
    unittest.main()
