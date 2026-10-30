import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import experiment_runner as runner  # noqa: E402


class MatrixNameCaseTests(unittest.TestCase):
    def run_matrix(self, root, names):
        (root / 'source').mkdir(exist_ok=True)
        rows = [{'name': name, 'source': str(root / 'source'), 'command': [sys.executable, '-c', 'pass']}
                for name in names]
        matrix = root / 'matrix.json'
        matrix.write_text(json.dumps(rows), encoding='utf-8')
        stderr = io.StringIO()
        with patch.object(sys, 'argv', ['runner', str(matrix), '--out', str(root / 'out')]), \
             patch.object(runner, 'run_trial', return_value={'status': 'pass'}) as trial, \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            try:
                code = runner.main()
            except SystemExit as error:
                code = error.code
        return code, trial, stderr.getvalue()

    def test_names_differing_only_by_case_run_no_trial(self):
        with tempfile.TemporaryDirectory() as directory:
            code, trial, stderr = self.run_matrix(Path(directory).resolve(), ['Trial', 'trial'])
        trial.assert_not_called()
        self.assertEqual(code, 2)
        self.assertIn('invalid experiment matrix', stderr)

    def test_distinct_names_still_reach_the_trial_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            code, trial, _ = self.run_matrix(Path(directory).resolve(), ['Trial-a', 'trial-b'])
        self.assertEqual(code, 0)
        self.assertEqual(trial.call_count, 2)


if __name__ == '__main__':
    unittest.main()
