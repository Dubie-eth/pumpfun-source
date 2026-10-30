"""Pump differentials must prepare nested output paths before running cases."""

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = tuple(
    ROOT / "scripts" / name
    for name in (
        "pump_create_nested_differential.py",
        "pump_creator_collect_v2_differential.py",
        "pump_earned_cashback_differential.py",
        "pump_fee_sweep_differential.py",
        "pump_global_init_differential.py",
        "pump_legacy_cashback_differential.py",
        "pump_minimum_fee_differential.py",
        "pump_set_params_differential.py",
        "pump_tokenkeg_two_curve_differential.py",
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


class PumpOutputParentTests(unittest.TestCase):
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
