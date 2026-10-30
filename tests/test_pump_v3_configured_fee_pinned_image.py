"""The v3 configured-fee differential binds every case and its receipt to one candidate image.

scripts/pump_v3_configured_fee_differential.py loads the candidate program
from a path on every case (run() calls LiteSVM.add_program_from_file with
the binary it is handed) but reads candidate_sha256 from that same live
path only after the loop. A build that replaces the candidate file mid-run
therefore mixes two images under a receipt that names only the final one.
main() must pin the candidate once, before the first case, so every case
load and the report hash read the same snapshot.
"""

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pump_v3_configured_fee_differential.py"


def main_function(tree):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node
    raise AssertionError("main() not found in pump_v3_configured_fee_differential.py")


def is_pin_of_candidate(node):
    """True for `a.candidate = pin_program(a.candidate)` (or a pinned alias)."""
    if not isinstance(node, ast.Assign):
        return False
    value = node.value
    if isinstance(value, ast.IfExp):
        value = value.body
    if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)):
        return False
    if value.func.id != "pin_program":
        return False
    return any(
        isinstance(arg, ast.Attribute)
        and isinstance(arg.value, ast.Name)
        and arg.value.id == "a"
        and arg.attr == "candidate"
        for arg in value.args
    )


class V3ConfiguredFeePinnedImageTests(unittest.TestCase):
    def test_main_pins_candidate_before_the_case_loop(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        imports_pin = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "pump_amm_reusable_harness"
            and any(alias.name == "pin_program" for alias in node.names)
            for node in ast.walk(tree)
        )
        self.assertTrue(imports_pin, "script must import pin_program")
        main = main_function(tree)
        pin_index = None
        loop_index = None
        for index, node in enumerate(main.body):
            if pin_index is None and is_pin_of_candidate(node):
                pin_index = index
            if loop_index is None and isinstance(node, ast.For):
                loop_index = index
        self.assertIsNotNone(pin_index, "main() must pin a.candidate via pin_program")
        self.assertIsNotNone(loop_index, "main() must loop over cases")
        self.assertLess(
            pin_index,
            loop_index,
            "the candidate must be pinned before the first case runs",
        )


if __name__ == "__main__":
    unittest.main()
