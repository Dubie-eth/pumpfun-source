"""One full Fees upsert matrix and shared bounded real-VM publication checks."""
import hashlib
import shutil
import unittest
from publication_cli_support import PublicationCase, ROOT


class FeesUpsertReportPublicationTests(PublicationCase, unittest.TestCase):
    NAMES=('fees_upsert_differential',)
    DATA=('evidence/upstream/pump_fees.json','evidence/original/pump_fees/deployed.so')
    HELPERS=('fees_config_differential','fees_admin_differential','fee_recovery_fixture')
    PROGRAM='evidence/original/pump_fees/deployed.so'
    EXPECTED={'fees_upsert_differential':578}

    def test_wrong_real_image_retains_failed_report(self):
        shutil.copyfile(ROOT/'evidence/original/mayhem/deployed.so',self.root/'candidate.so')
        result=self.invoke(self.NAMES[0])
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        report=self.report()
        self.assertEqual(report['case_count'],2)
        self.assertTrue(report['mismatches'])
        self.assertEqual(report['candidate_sha256'],hashlib.sha256((self.root/'candidate.so').read_bytes()).hexdigest())


if __name__=='__main__':unittest.main()
