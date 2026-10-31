"""Real error-message families use the admitted original and candidate images."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / 'evidence/original/pump_fees/deployed.so'
OTHER = ROOT / 'evidence/original/pump/deployed.so'
DRIVER = r'''
import sys, shutil
from pathlib import Path
scripts, original, candidate, baseline, replacement, output, mode = sys.argv[1:]
sys.path.insert(0, scripts)
import fees_error_messages_differential as module
module.ORIGINAL = Path(original)
returned = []
def hook(frame, event, arg):
    if event == 'return' and frame.f_code.co_name == 'run' and frame.f_code.co_filename == module.__file__:
        returned.append(1)
        if len(returned) == 3:
            sys.setprofile(None)
            for path in (original, candidate, baseline):
                shutil.copyfile(replacement, path)
if mode == 'mutate':
    sys.setprofile(hook)
sys.argv = [module.__file__, '--candidate', candidate, '--output', output]
if mode != 'without-baseline':
    sys.argv += ['--baseline', baseline]
try:
    module.main()
finally:
    sys.setprofile(None)
    if mode == 'mutate' and len(returned) < 3:
        raise RuntimeError('first original/candidate/baseline family never completed')
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class FeesErrorMessagesPinnedImageTests(unittest.TestCase):
    def staged_run(self, mode):
        temporary = tempfile.TemporaryDirectory(prefix='fees-error-binding-')
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        original, candidate, baseline = (directory / name for name in ('original.so', 'candidate.so', 'baseline.so'))
        for path in (original, candidate, baseline):
            shutil.copyfile(ORIGINAL, path)
        if mode == 'wrong-candidate':
            shutil.copyfile(OTHER, candidate)
        elif mode == 'wrong-baseline':
            shutil.copyfile(OTHER, baseline)
        output = directory / 'receipt.json'
        environment = dict(os.environ)
        environment.pop('PYTHONOPTIMIZE', None)
        result = subprocess.run(
            [sys.executable, '-B', '-c', DRIVER, str(ROOT / 'scripts'), str(original),
             str(candidate), str(baseline), str(OTHER), str(output), mode],
            cwd=ROOT, env=environment, text=True, capture_output=True, timeout=120,
        )
        return result, output, original, candidate, baseline

    def test_all_three_images_survive_replacement_between_families(self):
        result, output, original, candidate, baseline = self.staged_run('mutate')
        self.assertEqual(result.returncode, 0, result.stdout[-2000:] + result.stderr[-2000:])
        for path in (original, candidate, baseline):
            self.assertEqual(sha(path), sha(OTHER))
        report = json.loads(output.read_text(encoding='utf-8'))
        for field in ('original_sha256', 'candidate_sha256', 'baseline_sha256'):
            self.assertEqual(report[field], sha(ORIGINAL))
        self.assertEqual(report['case_count'], 2)
        self.assertEqual(report['mismatches'], [])
        for row in report['cases']:
            self.assertTrue(row['match'])
            self.assertEqual(row['baseline_error_messages'], row['original_error_messages'])
            for field in row['compared_fields']:
                self.assertEqual(row['baseline'][field], row['original'][field])

    def test_wrong_candidate_has_real_mismatches_and_fails(self):
        result, output, *_ = self.staged_run('wrong-candidate')
        self.assertEqual(result.returncode, 1, result.stderr[-2000:])
        self.assertTrue(output.exists(), result.stderr[-2000:])
        report = json.loads(output.read_text(encoding='utf-8'))
        self.assertEqual(report['candidate_sha256'], sha(OTHER))
        self.assertEqual(report['baseline_sha256'], sha(ORIGINAL))
        self.assertEqual(len(report['mismatches']), 2)

    def test_wrong_baseline_is_executed_and_reported(self):
        result, output, *_ = self.staged_run('wrong-baseline')
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        report = json.loads(output.read_text(encoding='utf-8'))
        self.assertEqual(report['baseline_sha256'], sha(OTHER))
        self.assertEqual(report['mismatches'], [])
        for row in report['cases']:
            self.assertNotEqual(row['baseline']['error'], row['original']['error'])
            self.assertNotEqual(row['baseline_error_messages'], row['original_error_messages'])

    def test_optional_baseline_remains_optional(self):
        result, output, *_ = self.staged_run('without-baseline')
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        report = json.loads(output.read_text(encoding='utf-8'))
        self.assertEqual(report['mismatches'], [])
        self.assertNotIn('baseline_sha256', report)
        self.assertTrue(all('baseline' not in row for row in report['cases']))


if __name__ == '__main__':
    unittest.main()
