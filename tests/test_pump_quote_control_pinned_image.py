"""`scripts/pump_quote_control_differential.py` must execute one candidate image per run.

Sibling of merged #2722 (pump create-control and IDL-authority
differentials) and the pinned-image family that followed it: this
script's `main()` passed the live `--candidate` path to `execute()`
once per case, and `execute()` hands the path straight to
`add_program_from_file`, which reads the file on every call — so
replacing the candidate file mid-run made later cases execute a
different image. Worse than its siblings, the report carried no
candidate hash at all, so the receipt did not even name the image
that ran.

The script module itself is not imported here (it needs solders and
the LiteSVM fixture); only the pinning wiring is checked by AST, so
the test fails on base (no `pin_program` use, no `candidate_sha256`
in the report) and passes with the fix. The runtime swap test of
#2722 is not runnable here (solders is absent).
"""

import ast
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPT = ROOT / "scripts" / "pump_quote_control_differential.py"


def load_tree():
    return ast.parse(SCRIPT.read_text(encoding="utf-8"))


def main_function(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node
    return None


class PumpQuoteControlPinnedImageTests(unittest.TestCase):
    def test_candidate_image_is_pinned_before_the_case_loop(self):
        tree = load_tree()
        imported = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "pump_amm_reusable_harness"
            and any(alias.name == "pin_program" for alias in node.names)
            for node in ast.walk(tree)
        )
        self.assertTrue(imported, "pin_program is not imported")

        main = main_function(tree)
        self.assertIsNotNone(main, "main() not found")
        pin_assign = None
        case_loop = None
        for node in ast.walk(main):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                func = node.value.func
                if isinstance(func, ast.Name) and func.id == "pin_program":
                    for target in node.targets:
                        if (
                            isinstance(target, ast.Attribute)
                            and target.attr == "candidate"
                        ):
                            pin_assign = node
            if isinstance(node, ast.For):
                # The case loop iterates cases().
                if isinstance(node.iter, ast.Call) and isinstance(
                    node.iter.func, ast.Name
                ) and node.iter.func.id == "cases":
                    case_loop = node
        self.assertIsNotNone(pin_assign, "main() does not pin a.candidate")
        self.assertIsNotNone(case_loop, "main() case loop not found")
        self.assertLess(
            pin_assign.lineno,
            case_loop.lineno,
            "candidate is pinned after the case loop starts",
        )

    def test_report_names_the_pinned_candidate(self):
        tree = load_tree()
        main = main_function(tree)
        self.assertIsNotNone(main, "main() not found")
        named = False
        for node in ast.walk(main):
            if isinstance(node, ast.Constant) and node.value == "candidate_sha256":
                named = True
        self.assertTrue(named, "report does not carry candidate_sha256")

    def test_cases_still_run_against_the_candidate(self):
        # Documents the base shape the pinning closes: main() passes
        # a.candidate to execute() for every case. After the fix that
        # value is the pinned snapshot, not the live path.
        tree = load_tree()
        main = main_function(tree)
        self.assertIsNotNone(main, "main() not found")
        per_case = False
        for node in ast.walk(main):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "execute"
            ):
                if len(node.args) >= 1 and isinstance(node.args[0], ast.Attribute):
                    if node.args[0].attr == "candidate":
                        per_case = True
        self.assertTrue(per_case, "main() does not pass a.candidate to execute()")


if __name__ == "__main__":
    unittest.main()
