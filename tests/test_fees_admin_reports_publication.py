"""Fees admin/config reports must publish atomically."""

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = tuple(
    ROOT / "scripts" / name
    for name in (
        "fees_admin_differential.py",
        "fees_admin_transfer_differential.py",
        "fees_config_differential.py",
    )
)


class FeesAdminReportsPublicationTests(unittest.TestCase):
    def test_receipts_use_pumpreport(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                tree = ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
                self.assertTrue(any(
                    isinstance(node, ast.ImportFrom)
                    and node.module == "pump_differential_output"
                    and any(alias.name == "PumpReport" for alias in node.names)
                    for node in tree.body
                ))
                assignments = []
                direct_writes = []
                publisher_writes = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign) and any(
                        isinstance(target, ast.Name) and target.id == "publisher"
                        for target in node.targets
                    ):
                        if (
                            isinstance(node.value, ast.Call)
                            and isinstance(node.value.func, ast.Name)
                            and node.value.func.id == "PumpReport"
                        ):
                            assignments.append(node.lineno)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                        if node.func.attr in {"write_text", "write_bytes"}:
                            value = node.func.value
                            if isinstance(value, ast.Attribute) and value.attr == "output":
                                direct_writes.append(node.lineno)
                        if node.func.attr == "write" and isinstance(node.func.value, ast.Name):
                            if node.func.value.id == "publisher":
                                publisher_writes.append(node.lineno)
                self.assertTrue(assignments)
                self.assertEqual(direct_writes, [])
                self.assertTrue(publisher_writes)
                self.assertLess(min(assignments), min(publisher_writes))


if __name__ == "__main__":
    unittest.main()
