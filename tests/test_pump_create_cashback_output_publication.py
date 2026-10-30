"""The creation and cashback differentials must not replace their own inputs."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
ORIGINAL = ROOT / 'evidence/original/pump/deployed.so'
NAMES = ('pump_create_differential.py', 'pump_cashback_differential.py')


class PumpReportPublicationTests(unittest.TestCase):
    def invoke(self, name, candidate, output):
        return subprocess.run(
            [sys.executable, '-B', str(SCRIPTS / name),
             '--candidate', str(candidate), '--output', str(output)],
            cwd=ROOT, capture_output=True, text=True, timeout=120)

    def fixture(self, root):
        candidate = root / 'candidate.so'
        shutil.copyfile(ORIGINAL, candidate)
        return candidate

    def test_output_aliasing_the_candidate_is_rejected(self):
        for name in NAMES:
            with self.subTest(script=name), tempfile.TemporaryDirectory() as temporary:
                candidate = self.fixture(Path(temporary))
                before = candidate.read_bytes()
                result = self.invoke(name, candidate, candidate)
                self.assertEqual(result.returncode, 1)
                self.assertIn('report output aliases an input', result.stderr)
                self.assertEqual(candidate.read_bytes(), before)

    def test_normal_output_is_still_published(self):
        for name in NAMES:
            with self.subTest(script=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                candidate = self.fixture(root)
                output = root / 'report.json.gz'
                result = self.invoke(name, candidate, output)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(output.read_bytes()[:2], b'\x1f\x8b')
                self.assertEqual(candidate.read_bytes(), ORIGINAL.read_bytes())


if __name__ == '__main__':
    unittest.main()
