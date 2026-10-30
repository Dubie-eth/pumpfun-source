"""Supplied --build-comparison handling in the claim-boundary and
incentive-schedule differentials: a null, empty or malformed comparison is
rejected before any case runs, and runs without the flag stay unbound."""
from contextlib import ExitStack, redirect_stdout
import gzip
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


claim = load('pump_claim_boundary_differential')
schedule = load('pump_incentive_schedule_differential')
INVALID = ['null', '{}', '[]', '0', '""', '{"comparison": null, "source_sha256": {}}',
           '{"comparison": {}, "source_sha256": null}']


class SuppliedBuildComparisonTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='supplied-build-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.candidate = self.root / 'candidate.so'
        self.candidate.write_bytes(b'candidate')
        self.runs = 0

    def result(self, fields):
        self.runs += 1
        return {**{key: 0 for key in fields}, 'transaction_base64': 't', 'logs': [], 'error': None}

    def invoke(self, module, build_text, output):
        arguments = ['driver', '--candidate', str(self.candidate), '--output', str(output)]
        if build_text is not None:
            build = self.root / 'build.json'
            build.write_text(build_text)
            arguments += ['--build-comparison', str(build)]
        with ExitStack() as stack:
            stack.enter_context(patch.object(sys, 'argv', arguments))
            stack.enter_context(redirect_stdout(io.StringIO()))
            if module is claim:
                stack.enter_context(patch.object(claim, 'cases', lambda seed: iter([{'name': 'one'}])))
                stack.enter_context(patch.object(claim, 'run_case', lambda path, case: self.result(claim.FIELDS)))
            else:
                stack.enter_context(patch.object(schedule, 'cases', lambda: iter([{'name': 'one'}])))
                stack.enter_context(patch.object(schedule.fixture, 'run', lambda case, path=None: self.result(schedule.FIELDS)))
            module.main()
        return json.loads(gzip.decompress(output.read_bytes()))

    def test_supplied_invalid_comparisons_are_rejected_before_any_case_runs(self):
        for module in (claim, schedule):
            for text in INVALID:
                with self.subTest(module=module.__name__, build=text):
                    self.runs = 0
                    output = self.root / f'{module.__name__}-{len(text)}-{abs(hash(text))}.json.gz'
                    with self.assertRaisesRegex(ValueError, 'invalid build comparison'):
                        self.invoke(module, text, output)
                    self.assertEqual(self.runs, 0)
                    self.assertFalse(output.exists())

    def test_control_without_comparison_still_publishes_unbound_report(self):
        for module in (claim, schedule):
            with self.subTest(module=module.__name__):
                report = self.invoke(module, None, self.root / f'{module.__name__}-none.json.gz')
                self.assertEqual(report['case_count'], 1)
                self.assertIsNone(report['build_comparison_sha256'])
                self.assertIsNone(report['compiled_source_sha256'])

    def test_control_wrong_candidate_comparison_is_still_refused(self):
        text = json.dumps({'comparison': {'candidate_sha256': '0' * 64}, 'source_sha256': {'x': '0' * 64}})
        for module in (claim, schedule):
            with self.subTest(module=module.__name__):
                with self.assertRaises(AssertionError):
                    self.invoke(module, text, self.root / f'{module.__name__}-wrong.json.gz')


if __name__ == '__main__':
    unittest.main()
