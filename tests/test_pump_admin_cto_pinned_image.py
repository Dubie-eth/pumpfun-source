"""The pump admin_cto differential binds every case and its receipt to one candidate image.

scripts/pump_admin_cto_differential.py loads the candidate program
from a path on every case (run() hands the path to
LiteSVM.add_program_from_file for the pump program) but reads the
report's candidate_sha256 from that same live path only after the
loop. Its pre-loop provenance block does not prevent the swap: it
hashes the candidate before the loop, so a build that replaces the
candidate file mid-run leaves a receipt whose provenance hash names
the old image, whose report hash names the new image, and whose
per-case results are split across both, with no field saying which
cases ran which image. main() must pin the candidate once, before
the provenance block, so every case load, the provenance hash, and
the report hash read the same snapshot.
"""

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pump_admin_cto_differential.py"


def main_function(tree):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node
    raise AssertionError("main() not found in pump_admin_cto_differential.py")


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


class PumpAdminCtoPinnedImageTests(unittest.TestCase):
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
