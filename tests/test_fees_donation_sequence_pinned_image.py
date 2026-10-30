"""The donation sequence binds its receipt to the candidate image it actually ran.

scripts/fees_donation_sequence.py loads the candidate program once, when
execute() builds its Fixture, and runs the whole deposit/crank sequence on
that one in-memory image. But the report's candidate_sha256 is read from the
live candidate path only after both sequences finish, so a build that
replaces the candidate file mid-run leaves a receipt naming an image that
never ran, while every case result came from the pre-swap bytes. The same
end-of-run hashing gap is what open #2877 closes for the captured loader;
this script is a sibling that #2877 cannot reach. main() must pin the
candidate once, before either sequence executes, so the loaded image and
the report hash read the same snapshot.
"""

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fees_donation_sequence.py"


def main_function(tree):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node
    raise AssertionError("main() not found in fees_donation_sequence.py")


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


def calls_execute(node):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "execute"
    )


class DonationSequencePinnedImageTests(unittest.TestCase):
    def test_main_pins_candidate_before_either_sequence_executes(self):
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
        execute_index = None
        for index, node in enumerate(main.body):
            if pin_index is None and is_pin_of_candidate(node):
                pin_index = index
            if execute_index is None and any(calls_execute(n) for n in ast.walk(node)):
                execute_index = index
        self.assertIsNotNone(pin_index, "main() must pin args.candidate via pin_program")
        self.assertIsNotNone(execute_index, "main() must execute sequences")
        self.assertLess(
            pin_index,
            execute_index,
            "the candidate must be pinned before the first sequence executes",
        )


if __name__ == "__main__":
    unittest.main()
