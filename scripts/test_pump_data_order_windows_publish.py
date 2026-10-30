#!/usr/bin/env python3
"""Data-order certificates must publish on Windows without hard links.

Sibling of merged #2908, which fixed the same defect in the diagnostic
auditor, and of open #2937, which fixed it for strict-ordered-log
receipts: those scripts staged a complete receipt and then unconditionally
hard-linked it to the output, and in a Windows sandbox os.link fails
with WinError 5, so no receipt was retained. This script published its
certificate the same way — an unconditional os.link in
publish_certificate().

Windows itself is not available here, so the Windows host is simulated
for the publish helper by patching os.name to 'nt' and making os.link
raise the sandbox error; the POSIX path is exercised for real through
publish_certificate(). The helper tests fail on base (no publish_file)
and pass with the fix; the wiring test fails on base
(publish_certificate() calls os.link directly).
"""
import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pump_data_order as gate  # noqa: E402


class DataOrderWindowsPublishTests(unittest.TestCase):
    def test_publish_file_uses_rename_on_windows(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staged = root / ".certificate.json.staged"
            staged.write_text('{"schema": 1}\n', encoding="utf-8")
            output = root / "certificate.json"
            with mock.patch.object(gate.os, "name", "nt"), \
                    mock.patch.object(gate.os, "link",
                                      side_effect=OSError("WinError 5")) as link:
                gate.publish_file(staged, output)
            link.assert_not_called()
            self.assertEqual(output.read_text(encoding="utf-8"),
                             '{"schema": 1}\n')
            self.assertFalse(staged.exists())

    def test_publish_certificate_uses_link_on_posix(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "certificate.json"
            cert = {"schema": 1, "payload": {"roles": ["role"]}}
            gate.publish_certificate(output, cert)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")),
                             cert)
            self.assertEqual([path.name for path in root.iterdir()],
                             [output.name])

    def test_publish_certificate_publishes_through_publish_file(self):
        source = Path(gate.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "publish_certificate")
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
