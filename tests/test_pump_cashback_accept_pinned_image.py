"""`scripts/pump_cashback_accept_differential.py` must execute one candidate image per run.

Sibling of merged #2722 (pump create-control and IDL-authority
differentials) and the buy-v2/sell-v2/legacy-sell pinning PRs, which pinned
their candidate images: this script's `main()` calls `v3.run()` once per
case with the raw candidate path, and `v3.run()` hands that path straight
to `add_program_from_file`, which reads the file on every call — so
replacing the candidate file mid-run makes later cases execute a
different image, while the report's `candidate_sha256` is read from the
candidate path only at the end. One receipt would then cover two images.
Unlike `v3`'s own `main()`, which pins its candidate, this script bypasses
that pinning by calling `v3.run()` directly.

The script module itself is not imported here (it needs solders and the
LiteSVM fixture); only the pinning wiring is checked by AST, so the test
fails on base (no `pin_program` use) and passes with the fix. The runtime
swap test of #2722 is not runnable here (solders is absent).
"""

import ast
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPT = ROOT / "scripts" / "pump_cashback_accept_differential.py"


def load_tree():
    return ast.parse(SCRIPT.read_text(encoding="utf-8"))


def main_body(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node.body
    raise AssertionError("main() not found")


class CashbackAcceptPinnedImageTests(unittest.TestCase):
    def test_candidate_pinned_before_case_loop(self):
        body = main_body(load_tree())
        pin_index = None
        loop_index = None
        for i, stmt in enumerate(body):
            if isinstance(stmt, ast.Assign) and any(
                isinstance(t, ast.Attribute)
                and t.attr == "candidate"
                for t in stmt.targets
            ):
                value = stmt.value
                if (
                    isinstance(value, ast.IfExp)
                    and isinstance(value.body, ast.Call)
                    and isinstance(value.body.func, ast.Name)
                    and value.body.func.id == "pin_program"
                ):
                    pin_index = i
            if isinstance(stmt, ast.For):
                loop_index = i
                break
        self.assertIsNotNone(pin_index, "main() never pins a.candidate")
        self.assertIsNotNone(loop_index, "main() has no case loop")
        self.assertLess(pin_index, loop_index, "pinning must precede the case loop")

    def test_pin_program_imported(self):
        tree = load_tree()
        imported = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "pump_amm_reusable_harness"
            and any(alias.name == "pin_program" for alias in node.names)
            for node in ast.walk(tree)
        )
        self.assertTrue(imported, "pin_program is not imported")


if __name__ == "__main__":
    unittest.main()
