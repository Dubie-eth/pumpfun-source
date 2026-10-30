"""The serial Pump aggregate must bound each suite with a killable process group."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/pump_validate_all.py'
ORIGINAL = ROOT / 'evidence/original/pump/deployed.so'


class PumpAggregateSuiteTimeoutTests(unittest.TestCase):
    def fixture(self, root):
        """Give the aggregate the candidate and producer receipts it binds."""
        candidate = root / 'candidate.so'
        shutil.copyfile(ORIGINAL, candidate)
        (root / 'build-comparison.json').write_text('{}')
        (root / 'build-attempt.json').write_text('{}')
        return candidate

    def invoke(self, candidate, output, timeout):
        return subprocess.run(
            [sys.executable, '-B', str(SCRIPT), '--candidate', str(candidate),
             '--output', str(output), '--suite-timeout', timeout],
            cwd=ROOT, capture_output=True, text=True, timeout=120)

    def test_expired_suite_is_killed_and_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = self.fixture(root)
            output = root / 'report.json.gz'
            result = self.invoke(candidate, output, '0.001')
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stderr.strip().splitlines()[-1], 'suite volume exceeded 0.001s')
            self.assertFalse(output.exists())

    def test_nonpositive_timeout_is_rejected(self):
        for timeout in ('0', '-1'):
            with self.subTest(timeout=timeout), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                candidate = self.fixture(root)
                output = root / 'report.json.gz'
                result = self.invoke(candidate, output, timeout)
                self.assertEqual(result.returncode, 1)
                self.assertIn('compiler timeout must be a positive finite number of seconds',
                              result.stderr)
                self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
