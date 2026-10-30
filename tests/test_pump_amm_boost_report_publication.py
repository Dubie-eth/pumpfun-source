"""`scripts/pump_amm_boost_differential.py` must publish its report safely.

Sibling of merged #3063 (AMM admin), #3042 (AMM buyback), #3054 (AMM
accumulator) and #3069 (AMM collect), which moved their report
publication behind `PumpReport`: this script's `main()` pinned the
candidate before running, then published with a bare
`args.output.write_text` and no alias check. With `--output` equal to
the user-supplied candidate path, the run succeeds (the candidate was
already pinned into a snapshot) and then replaces the user's candidate
file with report JSON; with `--output` equal to a retained original
image or a consumed fixture, the same unconditional write destroys
that input. The report hash still names the pinned snapshot, so the
loss is silent.

The script module itself is not imported here (it needs solders and
the LiteSVM fixture); the wiring is checked by AST, so the wiring
test fails on base (no `PumpReport` use) and passes with the fix.
The `PumpReport` mechanism tests run against the real publisher
module, which has no solders dependency. The full VM differential is
not runnable here (solders is absent).
"""

import ast
import os
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPT = ROOT / "scripts" / "pump_amm_boost_differential.py"

sys.path.insert(0, str(ROOT / "scripts"))
from pump_differential_output import PumpReport  # noqa: E402


def load_tree():
    return ast.parse(SCRIPT.read_text(encoding="utf-8"))


def main_source():
    tree = load_tree()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return ast.get_source_segment(SCRIPT.read_text(encoding="utf-8"), node)
    raise AssertionError("main() not found")


class BoostReportPublicationTests(unittest.TestCase):
    def test_report_is_published_through_pump_report(self):
        tree = load_tree()
        imported = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "pump_differential_output"
            and any(alias.name == "PumpReport" for alias in node.names)
            for node in ast.walk(tree)
        )
        self.assertTrue(imported, "PumpReport is not imported")

        source = main_source()
        # The publisher must be admitted before the candidate is pinned,
        # so the user-supplied candidate path itself is a protected input.
        publisher_at = source.index("PumpReport(")
        pin_at = source.index("pin_program(args.candidate)")
        self.assertLess(
            publisher_at, pin_at, "PumpReport must be built before pinning"
        )
        self.assertIn("args.output", source[publisher_at:publisher_at + 200])
        self.assertIn("args.candidate", source[publisher_at:publisher_at + 200])
        # Both consumed fixtures must be admitted as extra inputs.
        self.assertIn("amm-v2-trade-fixture.json", source)
        self.assertIn("curve-migrate-v2-signed-surfpool.json", source)
        # The report must go through the publisher, not a bare write.
        self.assertIn("publisher.write(", source)
        self.assertNotIn("args.output.write_text", source)
        self.assertNotIn("args.output.write_bytes", source)

    def test_publisher_rejects_input_aliases(self):
        with tempfile.TemporaryDirectory(prefix="boost-publication-") as tmp:
            root = Path(tmp)
            candidate = root / "candidate.so"
            candidate.write_bytes(b"candidate image")
            script = root / "boost.py"
            script.write_text("# boost differential\n")
            fixture = root / "fixture.json"
            fixture.write_text("{}\n")
            for output in (candidate, script, fixture):
                with self.subTest(output=output.name):
                    with self.assertRaisesRegex(
                        ValueError, "report output aliases an input"
                    ):
                        PumpReport(
                            output, root, candidate, script,
                            extra_inputs=[fixture],
                        )

    def test_publisher_stages_write_and_preserves_prior_on_failure(self):
        with tempfile.TemporaryDirectory(prefix="boost-publication-") as tmp:
            root = Path(tmp)
            candidate = root / "candidate.so"
            candidate.write_bytes(b"candidate image")
            script = root / "boost.py"
            script.write_text("# boost differential\n")
            output = root / "reports" / "output.json"
            publisher = PumpReport(output, root, candidate, script)
            publisher.write(b'{"case_count": 1}\n')
            self.assertEqual(output.read_bytes(), b'{"case_count": 1}\n')
            self.assertEqual(list(output.parent.iterdir()), [output])

            real_fsync = os.fsync

            def fail(fd):
                raise OSError("injected fsync failure")

            os.fsync = fail
            try:
                with self.assertRaises(OSError):
                    publisher.write(b'{"case_count": 2}\n')
            finally:
                os.fsync = real_fsync
            self.assertEqual(output.read_bytes(), b'{"case_count": 1}\n')
            self.assertEqual(list(output.parent.iterdir()), [output])


if __name__ == "__main__":
    unittest.main()
