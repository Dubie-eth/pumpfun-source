#!/usr/bin/env python3
"""The Mayhem initialize_mayhem_state differential must fail on candidate divergence.

Its exit status used to depend only on the original reaching the expected
signer gate, so a candidate that diverged on every case still exited 0. The
mismatching candidate here is a real program that is not Mayhem (the captured
Pump deployment loaded at the Mayhem address). The captured Mayhem original is
the control.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/mayhem_initialize_state_differential.py'


def run(candidate, output):
    return subprocess.run([sys.executable, '-B', str(SCRIPT), '--candidate', str(candidate),
                           '--output', str(output)], cwd=ROOT, capture_output=True,
                          text=True, encoding='utf-8')


class InitializeStateExitTests(unittest.TestCase):
    def test_both_images_remain_bound_after_input_replacement(self):
        expected = (ROOT / 'evidence/original/mayhem/deployed.so').read_bytes()
        replacement = (ROOT / 'evidence/original/pump/deployed.so').read_bytes()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            originals = root / 'evidence/original'
            (originals / 'mayhem').mkdir(parents=True)
            for name in ('pump', 'pump_fees'):
                (originals / name).mkdir()
                shutil.copyfile(ROOT / 'evidence/original' / name / 'deployed.so',
                                originals / name / 'deployed.so')
            for name in ('spl_token', 'spl_token_2022', 'associated_token'):
                target = root / 'evidence/dependencies' / name
                target.mkdir(parents=True)
                for file in ('capture.json', 'deployed.so'):
                    shutil.copyfile(ROOT / 'evidence/dependencies' / name / file, target / file)
            original = originals / 'mayhem/deployed.so'
            candidate = root / 'candidate.so'
            original.write_bytes(expected)
            candidate.write_bytes(expected)
            spec = importlib.util.spec_from_file_location('mayhem_init_bound', SCRIPT)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.ROOT = root
            execute = module.Fixture.execute
            calls = 0

            def mutate_after_pair(fixture, case):
                nonlocal calls
                result = execute(fixture, case)
                calls += 1
                if calls == 2:
                    original.write_bytes(replacement)
                    candidate.write_bytes(replacement)
                return result

            output = root / 'report.json'
            argv = [str(SCRIPT), '--candidate', str(candidate), '--output', str(output)]
            with mock.patch.object(sys, 'argv', argv), \
                    mock.patch.object(module.Fixture, 'execute', mutate_after_pair), \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as exited:
                    module.main()
            self.assertEqual(exited.exception.code, 0)
            report = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(report['mismatches'], [])
            self.assertEqual(report['case_count'], 5)
            self.assertEqual(report['original_sha256'], hashlib.sha256(expected).hexdigest())
            self.assertEqual(report['candidate_sha256'], hashlib.sha256(expected).hexdigest())

    def test_divergent_candidate_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'report.json'
            result = run(ROOT / 'evidence/original/pump/deployed.so', output)
            report = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(len(report['mismatches']), report['case_count'])
            self.assertEqual(result.returncode, 1, result.stdout[-300:] + result.stderr[-300:])

    def test_original_candidate_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'report.json'
            result = run(ROOT / 'evidence/original/mayhem/deployed.so', output)
            report = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(report['mismatches'], [])
            self.assertTrue(report['terminal_blocker_confirmed'])
            self.assertEqual(result.returncode, 0, result.stdout[-300:] + result.stderr[-300:])


if __name__ == '__main__':
    unittest.main()
