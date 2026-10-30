#!/usr/bin/env python3
"""The serial Fees aggregate must bound each suite with a killable process group."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/fees_validate_all.py'
CANDIDATE = ROOT / 'evidence/original/pump_fees/deployed.so'


class FeesSuiteTimeoutTests(unittest.TestCase):
    def invoke(self, output, timeout):
        return subprocess.run(
            [sys.executable, '-B', str(SCRIPT), '--candidate', str(CANDIDATE),
             '--output', str(output), '--suite-timeout', timeout],
            capture_output=True, text=True, timeout=120)

    def test_expired_suite_is_killed_and_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'report.json.gz'
            result = self.invoke(output, '0.001')
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stderr.strip().splitlines()[-1], 'suite queries exceeded 0.001s')
            self.assertFalse(output.exists())

    def test_nonpositive_timeout_is_rejected(self):
        for timeout in ('0', '-1'):
            with self.subTest(timeout=timeout), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / 'report.json.gz'
                result = self.invoke(output, timeout)
                self.assertEqual(result.returncode, 1)
                self.assertIn('compiler timeout must be a positive finite number of seconds',
                              result.stderr)
                self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
