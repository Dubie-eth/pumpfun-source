"""The virtual-reserve differential binds every case and its receipt to one candidate image.

scripts/pump_virtual_reserve_differential.py loads the candidate pump
program from a live path on every case (run() hands args.candidate to
LiteSVM.add_program_from_file) but reads the report's candidate_sha256 from
that same live path only after the loop. Its post-loop inputs assertion
covers the driver, the sibling module, the stub, and the fixtures, but not
the candidate, and the optional build-comparison check runs only before the
loop. So a build that replaces the candidate file mid-run leaves a receipt
whose report hash names the new image while the per-case results are split
across both images, with no field saying which cases ran which image.
main() must pin the candidate once, before the case loop, so every case
load and the report hash read the same snapshot.
"""

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pump_virtual_reserve_differential.py"


def main_function(tree):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node
    raise AssertionError("main() not found in pump_virtual_reserve_differential.py")


def is_pin_of_candidate(node):
    """True for `args.candidate = pin_program(args.candidate)` (or a pinned alias)."""
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
        and arg.value.id == "args"
        and arg.attr == "candidate"
        for arg in value.args
    )


class VirtualReservePinnedImageTests(unittest.TestCase):
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
        self.assertIsNotNone(pin_index, "main() must pin args.candidate via pin_program")
        self.assertIsNotNone(loop_index, "main() must loop over cases")
        self.assertLess(
            pin_index,
            loop_index,
            "the candidate must be pinned before the first case runs",
        )


if __name__ == "__main__":
    unittest.main()
