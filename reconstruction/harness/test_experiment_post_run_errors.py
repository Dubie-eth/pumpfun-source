"""A trial that fails its post-run checks must still leave an error receipt.

The matrix contract reports infrastructure problems as exit 2 with retained
attempts, so one bad trial cannot discard its evidence or stop the next trial.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from experiment_runner import run_trial

TOOL = Path(__file__).with_name('experiment_runner.py')
LINK_OUTPUT = ("import os, sys; print('finished'); "
               "os.symlink('/nonexistent', os.path.join(sys.argv[1], 'link'))")
LINK_SOURCE = "import os, sys; os.symlink('value', os.path.join(sys.argv[1], 'link'))"
REMOVE_INPUT = "import os, sys; os.unlink(sys.argv[1])"


class PostRunErrorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'value').write_text('source\n', encoding='utf-8')

    def assert_retained_error(self, destination, result, reason):
        self.assertEqual(result['status'], 'error')
        self.assertIn(reason, result['reason'])
        self.assertEqual(result['returncode'], 0)
        receipt = json.loads((destination / 'latest.json').read_text(encoding='utf-8'))
        self.assertEqual(receipt['attempt'], result['attempt'])
        self.assertEqual(receipt['status'], 'error')

    def test_output_symlink_is_a_retained_error(self):
        destination = self.root / 'trial'
        result = run_trial(self.source, [sys.executable, '-c', LINK_OUTPUT, '{out}'], destination)
        self.assert_retained_error(destination, result, 'output symlinks')
        log = destination / result['attempt'] / 'stdout.log'
        self.assertEqual(log.read_text(encoding='utf-8').strip(), 'finished')

    def test_source_link_added_during_the_run_is_a_retained_error(self):
        destination = self.root / 'trial'
        result = run_trial(self.source, [sys.executable, '-c', LINK_SOURCE, '{source}'], destination)
        self.assert_retained_error(destination, result, 'linked source inputs')

    def test_removed_declared_input_is_a_retained_error(self):
        declared = self.root / 'declared'
        declared.write_text('input\n', encoding='utf-8')
        destination = self.root / 'trial'
        result = run_trial(self.source, [sys.executable, '-c', REMOVE_INPUT, str(declared)],
                           destination, inputs=[declared])
        self.assert_retained_error(destination, result, 'declared')

    def test_matrix_reports_the_error_and_runs_the_next_trial(self):
        matrix = self.root / 'matrix.json'
        matrix.write_text(json.dumps([
            {'name': 'first', 'source': str(self.source),
             'command': [sys.executable, '-c', LINK_OUTPUT, '{out}']},
            {'name': 'second', 'source': str(self.source),
             'command': [sys.executable, '-c', 'pass']},
        ]), encoding='utf-8')
        out = self.root / 'trials'
        result = subprocess.run([sys.executable, '-B', str(TOOL), str(matrix), '--out', str(out)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual({name: row['status'] for name, row in report.items()},
                         {'first': 'error', 'second': 'pass'})


if __name__ == '__main__':
    unittest.main()
