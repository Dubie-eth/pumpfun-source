"""The AMM accumulator differential must publish without overwriting admitted inputs.

On base, main() ends with an unconditional ``a.output.write_text(...)`` and no
alias check, so ``--output`` equal to the candidate binary (whose bytes the
harness reads into the VM at construction) or to the retained original
evidence image silently replaces that input file with the report JSON. The
fix publishes through PumpReport, which rejects an output aliasing any
admitted input before any case runs.
"""

import ast
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pump_amm_accumulator_differential.py"


class PumpAmmAccumulatorReportPublicationTests(unittest.TestCase):
    def test_receipt_uses_pumpreport(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"), filename=str(SCRIPT))
        self.assertTrue(
            any(
                isinstance(node, ast.ImportFrom)
                and node.module == "pump_differential_output"
                and any(alias.name == "PumpReport" for alias in node.names)
                for node in tree.body
            )
        )
        main = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        )
        report_assignment = None
        direct_output_write = []
        publisher_write = []
        for node in ast.walk(main):
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "output"
                for target in node.targets
            ):
                if (
                    isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)
                    and node.value.func.id == "PumpReport"
                ):
                    report_assignment = node.lineno
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"write_text", "write_bytes"}:
                    value = node.func.value
                    if isinstance(value, ast.Attribute) and value.attr == "output":
                        direct_output_write.append(node.lineno)
                if node.func.attr == "write" and isinstance(node.func.value, ast.Name):
                    if node.func.value.id == "output":
                        publisher_write.append(node.lineno)
        self.assertIsNotNone(report_assignment)
        self.assertEqual(direct_output_write, [])
        self.assertTrue(publisher_write)
        self.assertLess(report_assignment, min(publisher_write))


if __name__ == "__main__":
    unittest.main()
