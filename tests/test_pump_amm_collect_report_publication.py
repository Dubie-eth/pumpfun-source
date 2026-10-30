"""Report publication tests for the AMM collect differential.

The collect differential published its report with a bare write_text and
no alias check, so --output equal to the candidate binary or the retained
original evidence image silently replaced that input with report JSON.
The fix publishes through PumpReport, which refuses an aliasing output
before any case runs. These tests exercise the real CLI (148 cases); they
need the solders runtime the CI environment provides.
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
FILES = ('scripts/pump_amm_collect_differential.py',
         'scripts/pump_amm_liquidity_differential.py',
         'scripts/pump_amm_admin_differential.py',
         'scripts/pump_amm_reusable_harness.py',
         'scripts/pump_differential_output.py',
         'evidence/original/pump_amm/deployed.so',
         'evidence/upstream/pump_amm.json',
         'evidence/dependencies/spl_token/deployed.so',
         'evidence/dependencies/spl_token_2022/deployed.so',
         'research/imported-lab/analysis/pump_fun/config-snapshot.json',
         'research/imported-lab/analysis/pump_fun/amm-v2-trade-fixture.json')


class AmmCollectPublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='amm-collect-publication-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        for name in FILES:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, path)
        shutil.copyfile(self.root / FILES[5], self.root / 'candidate.so')
        self.inputs = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.output = self.root / 'reports/output.json'

    def invoke(self, output):
        env = dict(os.environ)
        env.pop('PYTHONOPTIMIZE', None)
        script = str(self.root / 'scripts/pump_amm_collect_differential.py')
        return subprocess.run(
            [sys.executable, '-B', script, '--candidate', str(self.root / 'candidate.so'),
             '--output', str(output)],
            cwd=self.root, env=env, capture_output=True, text=True, timeout=180)

    def assert_inputs_unchanged(self):
        for path, data in self.inputs.items():
            self.assertEqual(path.read_bytes(), data, str(path))

    def test_cli_publishes_report(self):
        result = self.invoke(self.output)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(self.output.read_bytes())
        self.assertEqual(report['case_count'], 148)
        self.assertEqual(report['mismatches'], [])
        self.assert_inputs_unchanged()

    def test_output_aliasing_candidate_rejected(self):
        result = self.invoke(self.root / 'candidate.so')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('report output aliases an input', result.stderr)
        self.assert_inputs_unchanged()

    def test_output_aliasing_original_rejected(self):
        result = self.invoke(self.root / FILES[5])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('report output aliases an input', result.stderr)
        self.assert_inputs_unchanged()


if __name__ == '__main__':
    unittest.main()
