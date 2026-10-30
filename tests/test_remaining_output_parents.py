"""Verifier and fee outputs must prepare nested paths before expensive work."""

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = tuple(
    ROOT / "scripts" / name
    for name in (
        "pump_set_mayhem_virtual_params_differential.py",
        "pump_validate_authority.py",
        "pump_validate_config_admin.py",
        "pump_validate_sell_accounting.py",
        "pump_validate_volume.py",
        "validate_fee_selection.py",
        "validate_quote_fees.py",
        "verify_mayhem_buy.py",
        "verify_mayhem_buy_v2.py",
        "verify_mayhem_pump_swap.py",
        "verify_mayhem_sell.py",
        "verify_mayhem_sell_v2.py",
    )
)


def call_name(node):
    if not isinstance(node, ast.Call):
        return ""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def is_output_parent(path):
    return (
        isinstance(path, ast.Attribute)
        and path.attr == "parent"
        and isinstance(path.value, ast.Attribute)
        and path.value.attr == "output"
    )


class RemainingOutputParentTests(unittest.TestCase):
    def test_parent_is_created_before_report_publication(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                tree = ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
                mkdir_lines = []
                write_lines = []
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    name = call_name(node)
                    if (
                        name == "mkdir"
                        and isinstance(node.func, ast.Attribute)
                        and is_output_parent(node.func.value)
                    ):
                        mkdir_lines.append(node.lineno)
                    if (
                        name in {"write_text", "write_bytes", "open"}
                        and isinstance(node.func, ast.Attribute)
                    ):
                        target = node.func.value
                        if isinstance(target, ast.Attribute) and target.attr == "output":
                            write_lines.append(node.lineno)
                self.assertTrue(mkdir_lines, "output.parent.mkdir is missing")
                self.assertTrue(write_lines, "output publication was not found")
                self.assertLess(min(mkdir_lines), min(write_lines))


if __name__ == "__main__":
    unittest.main()
