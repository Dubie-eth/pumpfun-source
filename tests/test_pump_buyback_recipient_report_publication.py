"""Unmodified full buyback recipient corpus and publication controls."""
import hashlib
import json
import shutil
import unittest
import publication_cli_support as support
from publication_cli_support import PublicationCase, ROOT


class PumpBuybackRecipientReportPublicationTests(PublicationCase, unittest.TestCase):
    NAMES = ('pump_buyback_recipient_differential',)
    DATA = (
        'evidence/original/pump/deployed.so',
        'evidence/upstream/pump.json',
        'research/imported-lab/analysis/pump_fun/config-snapshot.json',
    )
    HELPERS = ('pump_differential_output', 'pump_validate_config_admin', 'pump_diagnostic_audit')
    PROGRAM = 'evidence/original/pump/deployed.so'
    EXPECTED = {'pump_buyback_recipient_differential': 42}

    def test_wrong_real_image_preserves_failed_report(self):
        shutil.copyfile(ROOT / 'evidence/original/mayhem/deployed.so', self.root / 'candidate.so')
        result = self.invoke(self.NAMES[0], mode='full')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = self.report()
        self.assertEqual(len(report['cases']), 42)
        self.assertTrue(report['mismatches'])
        self.assertEqual(report['candidate_sha256'], hashlib.sha256((self.root / 'candidate.so').read_bytes()).hexdigest())

    def test_compressed_output_format(self):
        output = self.root / 'report.json.gz'
        result = self.invoke(self.NAMES[0], mode='full', output=output)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(output.read_bytes()[:2], b'\x1f\x8b')


if __name__ == '__main__':
    unittest.main()
