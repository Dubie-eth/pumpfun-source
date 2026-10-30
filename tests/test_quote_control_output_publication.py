#!/usr/bin/env python3
"""The quote-control differential must not publish its report over an input."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/pump_quote_control_fresh_differential.py'
ORIGINAL = ROOT / 'evidence/original/pump/deployed.so'


class QuoteControlOutputPublicationTests(unittest.TestCase):
    def candidate(self, root):
        path = root / 'candidate.so'
        path.write_bytes(ORIGINAL.read_bytes())
        return path

    def invoke(self, candidate, output):
        return subprocess.run(
            [sys.executable, '-B', str(SCRIPT), '--candidate', str(candidate),
             '--output', str(output)],
            capture_output=True, text=True, timeout=120)

    def assert_rejected(self, candidate, output):
        before = candidate.read_bytes()
        result = self.invoke(candidate, output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('aliases an input', result.stderr)
        self.assertEqual(candidate.read_bytes(), before)

    def test_candidate_is_not_replaced_by_its_own_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate = self.candidate(Path(temporary))
            self.assert_rejected(candidate, candidate)

    def test_symlinked_report_is_not_written_through(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = self.candidate(root)
            output = root / 'report.json.gz'
            try:
                output.symlink_to(candidate)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f'symlinks are unavailable: {error}')
            self.assert_rejected(candidate, output)

    def test_hardlinked_report_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = self.candidate(root)
            output = root / 'report.json.gz'
            os.link(candidate, output)
            self.assert_rejected(candidate, output)


if __name__ == '__main__':
    unittest.main()
