#!/usr/bin/env python3
"""A diagnostic audit cannot attest to a report without paired logs."""
import contextlib
import copy
import gzip
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pump_diagnostic_audit as gate  # noqa: E402


class DiagnosticAuditCoverageTests(unittest.TestCase):
    def test_retained_receipt_requires_both_log_sources(self):
        root = Path(gate.__file__).resolve().parents[1]
        artifact = root / 'research/handler-closure-multihop-mayhem-20261029/receipts/multi_hop_three_curve_cu14.json.gz'
        retained = artifact.read_bytes()
        self.assertEqual(hashlib.sha256(retained).hexdigest(),
                         '1b9212cf8107193430d77f1f48773f172ff94c77fe4cbad985945201ea338a8c')
        document = json.loads(gzip.decompress(retained))
        self.assertEqual(len(document['cases']), 50)
        for missing in (None, 'original', 'candidate'):
            for compressed in (False, True):
                with self.subTest(missing=missing, gzip=compressed), tempfile.TemporaryDirectory() as temporary:
                    directory = Path(temporary)
                    report = copy.deepcopy(document)
                    if missing:
                        del report['cases'][0][missing]['logs']
                    raw = json.dumps({'suites': {'retained': report}}).encode('utf-8')
                    raw = gzip.compress(raw, mtime=0) if compressed else raw
                    source, output = directory / 'report.json', directory / 'audit.json'
                    source.write_bytes(raw)
                    command = [sys.executable, *(['-O'] if sys.flags.optimize else []),
                               str(Path(gate.__file__).resolve()), '--report', str(source),
                               '--output', str(output)]
                    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
                    if missing:
                        self.assertNotEqual(result.returncode, 0, result.stdout)
                        self.assertIn(f'missing {missing} logs', result.stderr)
                        self.assertFalse(output.exists())
                    else:
                        self.assertEqual(result.returncode, 0, result.stderr)
                        audit = json.loads(output.read_bytes())
                        self.assertEqual(audit['log_bearing_cases'], 50)
                        self.assertEqual(audit['mismatches'], [])
                    self.assertEqual(source.read_bytes(), raw)
                    self.assertEqual(list(directory.glob('.audit.json.*')), [])
        self.assertEqual(artifact.read_bytes(), retained)

    def test_one_sided_nested_logs_are_rejected(self):
        for missing in ('original', 'candidate'):
            with self.subTest(missing=missing):
                pair = {side: {'metadata': {'logs': ['Program log: same']}}
                        for side in ('original', 'candidate')}
                del pair[missing]['metadata']['logs']
                with self.assertRaisesRegex(ValueError, f'missing {missing} logs'):
                    gate.audit({'suite': [pair]})

    def test_explicit_empty_log_lists_remain_available(self):
        for empty in ('original', 'candidate'):
            with self.subTest(empty=empty):
                pair = {side: {'logs': ['Program log: same']}
                        for side in ('original', 'candidate')}
                pair[empty]['logs'] = []
                self.assertEqual(self.audit({'suite': [pair]}), (False, True))

    def audit(self, suites):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = root / 'report.json'
            output = root / 'audit.json'
            report.write_text(json.dumps({'suites': suites}), encoding='utf-8')
            argv = ['pump_diagnostic_audit.py', '--report', str(report), '--output', str(output)]
            with mock.patch.object(sys, 'argv', argv), \
                    contextlib.redirect_stdout(io.StringIO()):
                try:
                    return gate.main(), output.exists()
                except ValueError as error:
                    self.assertIn('no paired logs', str(error))
                    return None, output.exists()

    def test_report_without_paired_logs_is_rejected_without_a_receipt(self):
        for suites in ({},
                       {'suite': []},
                       {'suite': [{'name': 'case', 'result': 'passed'}]},
                       {'suite': [{'original': {'logs': []}, 'candidate': {'logs': []}}]}):
            with self.subTest(suites=suites):
                self.assertEqual(self.audit(suites), (None, False))

    def test_report_with_paired_logs_keeps_its_result(self):
        pair = {'original': {'logs': ['Program log: same']},
                'candidate': {'logs': ['Program log: same']}}
        self.assertEqual(self.audit({'suite': [pair]}), (False, True))


if __name__ == '__main__':
    unittest.main()
