#!/usr/bin/env python3
"""An empty --source-directory must not produce a source-less differential report."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import pump_validate_all as aggregate  # noqa: E402

CANDIDATE = ROOT / 'evidence/original/pump/deployed.so'
SUITES = ('pump_validate_buy.py', 'pump_validate_quote.py', 'pump_validate_sell.py',
          'pump_validate_config_admin.py', 'pump_validate_authority.py')


class EmptySourceBindingTests(unittest.TestCase):
    def test_each_suite_refuses_an_empty_source_directory(self):
        for script in SUITES:
            with self.subTest(script=script), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                empty = root / 'empty'
                empty.mkdir()
                output = root / 'report.json.gz'
                result = subprocess.run(
                    [sys.executable, '-B', str(SCRIPTS / script),
                     '--candidate', str(CANDIDATE),
                     '--source-directory', str(empty), '--output', str(output)],
                    capture_output=True, text=True, timeout=120)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stderr.strip().splitlines()[-1],
                                 'no Rust/Cargo inputs under ' + str(empty))
                self.assertFalse(output.exists())

    def test_aggregate_refuses_before_launching_a_suite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            empty = root / 'empty'
            empty.mkdir()
            candidate = root / 'candidate.so'
            candidate.write_bytes(CANDIDATE.read_bytes())
            build_report = root / 'build-comparison.json'
            build_report.write_text(json.dumps({
                'comparison': {'candidate_sha256': '0' * 64}, 'source_sha256': {}}))
            (root / 'build-attempt.json').write_text('{}')
            argv = ['pump_validate_all.py', '--candidate', str(candidate),
                    '--build-report', str(build_report),
                    '--source-directory', str(empty),
                    '--output', str(root / 'report.json.gz')]
            launched = []

            def refuse(*args, **kwargs):
                launched.append(args)
                raise AssertionError('a suite was launched')

            with mock.patch.object(sys, 'argv', argv), \
                    mock.patch.object(aggregate.subprocess, 'run', refuse):
                with self.assertRaisesRegex(SystemExit, 'no Rust/Cargo inputs under'):
                    aggregate.main()
            self.assertEqual(launched, [])


if __name__ == '__main__':
    unittest.main()
