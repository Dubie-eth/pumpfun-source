#!/usr/bin/env python3
"""The revalidation audit must not report an uninvoked verifier as a failure."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import revalidate_all as revalidate

REQUIRES_IMAGES = """import argparse
ap = argparse.ArgumentParser()
ap.add_argument('--images', required=True)
ap.parse_args()
print('ran')
"""

FAILS = """print('evidence differs')
raise SystemExit(1)
"""

PASSES = """print('ok')
"""


class RequiredArgumentTests(unittest.TestCase):
    def test_usage_error_names_every_required_option(self):
        output = ("usage: verify.py [-h] --images IMAGES [--root ROOT]\n"
                  "verify.py: error: the following arguments are required: "
                  "--images, --root")
        self.assertEqual(revalidate.required_arguments(output),
                         ['--images', '--root'])

    def test_other_output_names_no_required_option(self):
        self.assertEqual(revalidate.required_arguments('evidence differs'), [])
        self.assertEqual(revalidate.required_arguments('Traceback (most recent call last):'), [])


class RunVerifyTests(unittest.TestCase):
    def packet(self, source):
        temporary = tempfile.TemporaryDirectory(prefix='revalidate-invocation-')
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        (directory / 'verify.py').write_text(source, encoding='utf-8')
        return directory

    def test_missing_required_argument_is_not_a_failure(self):
        result = revalidate.run_verify(self.packet(REQUIRES_IMAGES))
        self.assertEqual(result['status'], 'not_invoked')
        self.assertEqual(result['required'], ['--images'])

    def test_evidence_disagreement_stays_a_failure(self):
        result = revalidate.run_verify(self.packet(FAILS))
        self.assertEqual(result['status'], 'fail')

    def test_successful_verifier_still_passes(self):
        result = revalidate.run_verify(self.packet(PASSES))
        self.assertEqual(result['status'], 'pass')


class ReportTests(unittest.TestCase):
    def results(self):
        return [
            {'packet': 'passes', 'has_verify': True, 'has_manifest': False,
             'manifest_check': {'status': 'skipped'},
             'verify_check': {'status': 'pass'}, 'overall': 'pass'},
            {'packet': 'uninvoked', 'has_verify': True, 'has_manifest': True,
             'manifest_check': {'status': 'pass', 'errors': []},
             'verify_check': {'status': 'not_invoked', 'required': ['--images']},
             'overall': 'not_invoked'},
            {'packet': 'fails', 'has_verify': True, 'has_manifest': False,
             'manifest_check': {'status': 'skipped'},
             'verify_check': {'status': 'fail', 'output': 'evidence differs'},
             'overall': 'fail'},
        ]

    def test_uninvoked_packets_are_listed_separately(self):
        temporary = tempfile.TemporaryDirectory(prefix='revalidate-report-')
        self.addCleanup(temporary.cleanup)
        output = Path(temporary.name)
        revalidate.write_reports(output, [], self.results(), 1, 1, 0, 1, 1.0)
        summary = json.loads((output / 'summary.json').read_text())
        self.assertEqual(summary['not_invoked'], 1)
        self.assertEqual(summary['failed_packets'][0]['packet'], 'fails')
        self.assertEqual(summary['not_invoked_packets'],
                         [{'packet': 'uninvoked', 'required': ['--images']}])
        self.assertEqual(json.loads((output / 'failed.json').read_text()), ['fails'])
        self.assertEqual(json.loads((output / 'not-invoked.json').read_text()),
                         ['uninvoked'])
        self.assertEqual(json.loads((output / 'passed.json').read_text()), ['passes'])
        self.assertIn('Not invoked', (output / 'README.md').read_text())


if __name__ == '__main__':
    unittest.main()
