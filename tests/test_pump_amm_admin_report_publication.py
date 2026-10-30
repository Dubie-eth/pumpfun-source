"""Report publication tests for the AMM admin differential.

The admin differential loads the candidate binary into memory at harness
construction and hashes it, then used to publish its report with a bare
write_text: --output equal to the candidate, the retained original image,
or a hashed source file silently replaced that input with report JSON.
The fix publishes through PumpReport, which refuses an aliasing output
before any case runs. These tests exercise the real CLI in --quick mode
(267 cases); they need the solders runtime the CI environment provides.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILES = ('scripts/pump_amm_admin_differential.py',
         'scripts/pump_differential_output.py',
         'evidence/original/pump_amm/deployed.so',
         'evidence/upstream/pump_amm.json',
         'research/imported-lab/analysis/pump_fun/config-snapshot.json')


class AmmAdminPublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='amm-admin-publication-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        for name in FILES:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, path)
        source = self.root / 'programs/pump-amm/lib.rs'
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text('// hashed source input\n')
        shutil.copyfile(self.root / FILES[2], self.root / 'candidate.so')
        self.inputs = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.output = self.root / 'reports/output.json'

    def invoke(self, output):
        env = dict(os.environ)
        env.pop('PYTHONOPTIMIZE', None)
        script = str(self.root / 'scripts/pump_amm_admin_differential.py')
        return subprocess.run(
            [sys.executable, '-B', script, '--candidate', str(self.root / 'candidate.so'),
             '--output', str(output), '--quick'],
            cwd=self.root, env=env, capture_output=True, text=True, timeout=120)

    def assert_inputs_unchanged(self):
        for path, data in self.inputs.items():
            self.assertEqual(path.read_bytes(), data, str(path))

    def test_quick_cli_publishes_report(self):
        result = self.invoke(self.output)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(self.output.read_bytes())
        self.assertEqual(report['case_count'], 267)
        self.assertEqual(report['mismatches'], [])
        self.assert_inputs_unchanged()

    def test_output_aliasing_candidate_rejected(self):
        result = self.invoke(self.root / 'candidate.so')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('report output aliases an input', result.stderr)
        self.assert_inputs_unchanged()

    def test_output_aliasing_original_rejected(self):
        result = self.invoke(self.root / FILES[2])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('report output aliases an input', result.stderr)
        self.assert_inputs_unchanged()

    def test_output_aliasing_source_rejected(self):
        result = self.invoke(self.root / 'programs/pump-amm/lib.rs')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('report output aliases an input', result.stderr)
        self.assert_inputs_unchanged()


if __name__ == '__main__':
    unittest.main()
