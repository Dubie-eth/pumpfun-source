import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import minimize_experiment as minimizer  # noqa: E402


class InitialPredicateReportTests(unittest.TestCase):
    def test_report_separates_infrastructure_error_from_unmet_predicate(self):
        for status in ('fail', 'error'):
            with self.subTest(status=status):
                result = minimizer.minimize(2, lambda items: status, 5)
                self.assertEqual(result['status'], 'initial-predicate-not-met')
                self.assertEqual(result.get('wanted'), 'pass')
                self.assertEqual(result.get('tested'), [{'selected': [0, 1], 'status': status}])

    def test_cli_report_names_the_failed_initial_trial(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'source').mkdir()
            (root / 'source/lib.rs').write_text('fn main() {}\n', encoding='utf-8')
            patch_file = root / 'unit.patch'
            patch_file.write_text('--- a/missing.rs\n+++ b/missing.rs\n@@ -1 +1 @@\n-old\n+new\n', encoding='utf-8')
            patches = root / 'patches.json'
            patches.write_text(json.dumps([str(patch_file)]), encoding='utf-8')
            oracle = root / 'oracle.json'
            oracle.write_text(json.dumps({'command': [sys.executable, '-c', 'pass']}), encoding='utf-8')
            argv = ['minimize', '--source', str(root / 'source'), '--patches', str(patches),
                    '--oracle', str(oracle), '--out', str(root / 'out')]
            with patch.object(sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(minimizer.main(), 2)
            report = json.loads((root / 'out/minimized.json').read_text(encoding='utf-8'))
        self.assertEqual(report['status'], 'initial-predicate-not-met')
        self.assertEqual(report.get('tested'), [{'selected': [0], 'status': 'error'}])


if __name__ == '__main__':
    unittest.main()
