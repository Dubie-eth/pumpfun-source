"""Admin incentive reports must not overwrite candidate or build evidence."""

import ast
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pump_admin_token_incentives_differential.py"


class PumpAdminTokenIncentivesReportPublicationTests(unittest.TestCase):
    def test_receipt_uses_pumpreport(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"), filename=str(SCRIPT))
        self.assertTrue(any(
            isinstance(node, ast.ImportFrom)
            and node.module == "pump_differential_output"
            and any(alias.name == "PumpReport" for alias in node.names)
            for node in tree.body
        ))
        main = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        )
        assignments = []
        direct_writes = []
        publisher_writes = []
        for node in ast.walk(main):
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
                    if isinstance(value, ast.Name) and value.id == "output":
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
