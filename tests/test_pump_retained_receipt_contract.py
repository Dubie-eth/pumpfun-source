"""Retained successes require typed claims, distinct cases and matching promised fields."""
import copy
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pump_validate_all as base
import pump_validate_parallel as parallel

# This is the comparison list emitted by the maintained QuoteControl producer.
KEYS = ['error', 'before_accounts', 'after_accounts', 'rollback', 'event_payloads',
        'inner_instructions', 'return_data', 'transaction_base64',
        'signature_verification', 'blockhash', 'sigverify_enabled', 'blockhash_check_enabled']


class CapturedAdministrativeReceiptContract(unittest.TestCase):
    """Exercise admission with the real producer and retained local program."""

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        root = Path(__file__).resolve().parents[1]
        cls.artifact = root / 'evidence/original/pump/deployed.so'
        output = Path(cls.temporary.name) / 'administration.json'
        subprocess.run([sys.executable, '-B', str(root / 'scripts/pump_validate_admin.py'),
                        '--candidate', str(cls.artifact), '--output', str(output)],
                       cwd=root, capture_output=True, text=True, check=True, timeout=60)
        cls.report = json.loads(output.read_bytes())

    def validate(self, report):
        base.validate_case_results(report, 'administration')
        return parallel.validate_result('administration', report, self.artifact, self.artifact)

    def test_producer_receipt_is_admitted(self):
        self.assertEqual(self.report['case_count'], 93)
        self.assertEqual(self.report['mismatches'], [])
        self.assertEqual(self.validate(self.report), 93)

    def test_retained_error_balance_and_bytes_must_match(self):
        for field, changed in [('error', 'unexpected failure'), ('lamports', 1), ('data_hex', 'ff')]:
            with self.subTest(field=field):
                report = copy.deepcopy(self.report)
                report['cases'][0]['candidate'][field] = changed
                with self.assertRaisesRegex(AssertionError, 'retained comparison contradicts'):
                    self.validate(report)

    def test_removing_a_promised_field_cannot_preserve_success(self):
        for field in ('error', 'lamports', 'data_hex'):
            for sides in [('original',), ('candidate',), ('original', 'candidate')]:
                with self.subTest(field=field, sides=sides):
                    report = copy.deepcopy(self.report)
                    for side in sides:
                        del report['cases'][0][side][field]
                    with self.assertRaisesRegex(AssertionError, 'compared field .* missing'):
                        self.validate(report)

    def test_incidental_diagnostics_are_not_promised_equal(self):
        report = copy.deepcopy(self.report)
        report['cases'][0]['candidate']['logs'].append('Program log: incidental diagnostic')
        report['cases'][0]['original']['compute_units'] = 1
        report['cases'][0]['candidate']['compute_units'] = 2
        self.assertEqual(self.validate(report), 93)

    def test_every_generic_suite_has_a_comparison_contract(self):
        specialized = {'quote_control', 'multi_hop_curve_partial', 'tokenkeg_two_curve'}
        self.assertEqual(set(base.CASE_COMPARE_KEYS), set(base.EXPECTED_CASES) - specialized)


def quote_rows(count):
    return [{'case': f'fixture/{index}', 'matches': True, 'different_fields': [],
             'original': {**dict.fromkeys(KEYS), 'compute_units': 1},
             'candidate': {**dict.fromkeys(KEYS), 'compute_units': 2}}
            for index in range(count)]


class RetainedReceiptContract(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.artifact = Path(temporary.name).resolve() / 'program.so'
        self.artifact.write_bytes(b'fixture')
        self.report = {'bound_inputs_sha256': {str(self.artifact): base.sha(self.artifact)},
                       'cases': 507, 'results': quote_rows(507), 'compare_keys': KEYS,
                       'mismatches': 0}

    def validate(self, report=None):
        return parallel.validate_result('quote_control', report or self.report,
                                        self.artifact, self.artifact)

    def test_valid_protocol_keeps_incidental_compute_differences(self):
        self.assertEqual(self.validate(), 507)

    def test_success_is_a_boolean_not_a_truthy_claim(self):
        for value in ['false', 'true', 1, [], {}]:
            with self.subTest(value=value):
                report = copy.deepcopy(self.report)
                report['results'][0]['matches'] = value
                with self.assertRaises(AssertionError):
                    self.validate(report)

    def test_counts_are_actual_integers(self):
        report = copy.deepcopy(self.report)
        report['cases'] = 507.0
        with self.assertRaises(AssertionError):
            self.validate(report)
        for value in [True, 1.0, '1']:
            with self.subTest(value=value), self.assertRaises(AssertionError):
                base.retained_case_count({'cases': [{}], 'case_count': value})

    def test_repeating_a_case_cannot_replace_an_omitted_scenario(self):
        self.report['results'][-1] = copy.deepcopy(self.report['results'][0])
        with self.assertRaisesRegex(AssertionError, 'duplicate'):
            self.validate()

    def test_missing_scenario_id_is_rejected(self):
        del self.report['results'][0]['case']
        with self.assertRaises(AssertionError):
            self.validate()

    def test_empty_difference_claim_cannot_contradict_paired_outcomes(self):
        for field in KEYS:
            with self.subTest(field=field):
                report = copy.deepcopy(self.report)
                report['results'][0]['candidate'][field] = 'changed'
                with self.assertRaisesRegex(AssertionError, 'comparison'):
                    self.validate(report)

    def test_missing_compared_fields_or_weakened_compare_keys_are_rejected(self):
        for missing in [False, True]:
            with self.subTest(missing=missing):
                report = copy.deepcopy(self.report)
                if missing:
                    del report['results'][0]['candidate']['error']
                else:
                    report['compare_keys'] = ['error']
                with self.assertRaises(AssertionError):
                    self.validate(report)

    def test_two_curve_success_and_counts_are_typed(self):
        report = {'candidate_sha256': 'candidate',
                  'provenance': {'repository_inputs': {'evidence/original/pump/deployed.so': 'original'}},
                  'inputs_unchanged': True, 'case_count': 20, 'original_successes': 16,
                  'original_pump_cpi_cases': 18, 'verified_outer_signatures': 40,
                  'cases': [{'candidate': {}, 'mismatches': []} for _ in range(20)]}
        self.assertEqual(base.validate_two_curve(report, 'candidate', 'original'), 20)
        for key, value in [('inputs_unchanged', 'false'), ('case_count', 20.0),
                           ('original_successes', 16.0), ('verified_outer_signatures', 40.0)]:
            with self.subTest(key=key), self.assertRaises(AssertionError):
                base.validate_two_curve(report | {key: value}, 'candidate', 'original')


    def test_partial_curve_counts_are_typed(self):
        digest = base.sha(self.artifact)
        report = {'candidate_sha256': digest, 'original_pump_sha256': digest,
                  'passed': 56, 'case_count': 56, 'cases': [{'mismatches': []} for _ in range(56)]}
        self.assertEqual(parallel.validate_result('multi_hop_curve_partial', report,
                                                  self.artifact, self.artifact), 56)
        for key in ['passed', 'case_count']:
            with self.subTest(key=key), self.assertRaises(AssertionError):
                parallel.validate_result('multi_hop_curve_partial', report | {key: 56.0},
                                         self.artifact, self.artifact)

    def test_loader_success_flags_and_sizes_are_typed(self):
        path = self.artifact.with_name('loader.json')
        row = {'elf_sha256': base.sha(self.artifact), 'program_bytes': 36,
               'program_owner': 'BPFLoaderUpgradeab1e11111111111111111111111',
               'programdata_bytes': 10485760, 'elf_prefix_unchanged': True,
               'zero_allocation_tail': True}
        receipt = {'loads': [row], 'harness': str(self.artifact),
                   'input_sha256': {str(self.artifact): base.sha(self.artifact)}}
        path.write_text(json.dumps(receipt))
        parallel.validate_loader_receipt('fixture', path, self.artifact,
                                          self.artifact, self.artifact, [])
        for key, value in [('program_bytes', 36.0), ('programdata_bytes', 10485760.0),
                           ('elf_prefix_unchanged', 'false'), ('zero_allocation_tail', 1)]:
            with self.subTest(key=key), self.assertRaises(AssertionError):
                path.write_text(json.dumps(receipt | {'loads': [row | {key: value}]}))
                parallel.validate_loader_receipt('fixture', path, self.artifact,
                                                  self.artifact, self.artifact, [])


if __name__ == '__main__':
    unittest.main()
