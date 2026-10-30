"""AST + PumpReport mechanism controls for the Fees upsert report publication.

The upsert differential needs solders to run its VM cases, which this
environment lacks, so these controls verify the publication wiring
statically and exercise PumpReport's alias/staging guarantees directly,
mirroring the Fees social claim v2 publication test's approach.
"""
import ast
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/fees_upsert_differential.py'
sys.path.insert(0, str(ROOT / 'scripts'))
import pump_differential_output as publication
from pump_differential_output import PumpReport


class FeesUpsertReportPublicationTests(unittest.TestCase):
    def test_script_publishes_through_pump_report(self):
        src = SCRIPT.read_text(encoding='utf-8')
        tree = ast.parse(src)
        self.assertIn('from pump_differential_output import PumpReport', src)
        self.assertNotIn('.write_text(', src)
        self.assertIn('publisher.write(', src)
        main = next(n for n in tree.body
                    if isinstance(n, ast.FunctionDef) and n.name == 'main')
        calls = [n for n in ast.walk(main)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == 'PumpReport']
        self.assertEqual(len(calls), 1)
        loop = next(n for n in ast.walk(main)
                    if isinstance(n, ast.For))
        # The publisher is constructed before any case runs, so an aliased
        # output is rejected before the VM work starts.
        self.assertLess(calls[0].lineno, loop.lineno)

    def test_alias_outputs_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate = root / 'candidate.so'
            candidate.write_bytes(b'candidate')
            fixture = root / 'fixture.json'
            fixture.write_bytes(b'{}')
            with self.assertRaises(ValueError):
                PumpReport(candidate, root, candidate, __file__)
            with self.assertRaises(ValueError):
                PumpReport(fixture, root, candidate, __file__,
                           extra_inputs=[fixture])

    def test_staged_write_preserves_prior_report_on_fsync_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / 'reports' / 'output.json'
            report = PumpReport(output, root, None, __file__)
            report.write(b'first report\n')
            self.assertEqual(output.read_bytes(), b'first report\n')
            original_fsync = publication.os.fsync

            def fail(fd):
                raise OSError('injected fsync failure')

            publication.os.fsync = fail
            try:
                with self.assertRaises(OSError):
                    report.write(b'second report\n')
            finally:
                publication.os.fsync = original_fsync
            self.assertEqual(output.read_bytes(), b'first report\n')
            self.assertEqual([p for p in output.parent.iterdir()
                              if p.name.startswith('.output')], [])


if __name__ == '__main__':
    unittest.main()
