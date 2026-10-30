"""Research revalidation reports are published as one complete packet."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import revalidate_all as runner


class RevalidateAllAtomicPublicationTests(unittest.TestCase):
    def invoke(self, repo, output):
        argv = [
            str(Path(runner.__file__)),
            '--output', str(output),
        ]
        with mock.patch.object(runner, 'REPO', repo), \
                mock.patch.object(sys, 'argv', argv):
            runner.main()

    def repository(self, root):
        repo = root / 'repo'
        (repo / 'research/first').mkdir(parents=True)
        return repo

    def test_late_report_failure_leaves_no_partial_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self.repository(root)
            output = root / 'audit'
            original_write = Path.write_text

            def fail_summary(path, *args, **kwargs):
                if path.name == 'summary.json':
                    raise OSError('injected summary write failure')
                return original_write(path, *args, **kwargs)

            with mock.patch.object(Path, 'write_text', fail_summary):
                with self.assertRaisesRegex(
                        OSError, 'injected summary write failure'):
                    self.invoke(repo, output)

            self.assertFalse(
                output.exists(),
                'failed revalidation published partial reports')
            self.assertEqual(list(root.glob('.audit.staging-*')), [])

    def test_complete_audit_publishes_manifest_and_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self.repository(root)
            output = root / 'audit'

            self.invoke(repo, output)

            self.assertEqual(
                sorted(path.name for path in output.iterdir()),
                [
                    'README.md', 'failed.json', 'manifest.json',
                    'passed.json', 'results.json', 'skipped.json',
                    'summary.json', 'verify.py',
                ],
            )
            self.assertEqual(
                json.loads((output / 'results.json').read_text()),
                [{
                    'packet': 'first',
                    'has_verify': False,
                    'has_manifest': False,
                    'manifest_check': {'status': 'skipped'},
                    'verify_check': {'status': 'skipped'},
                    'overall': 'no_verification',
                }],
            )
            self.assertEqual(list(root.glob('.audit.staging-*')), [])

    def test_existing_audit_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self.repository(root)
            output = root / 'audit'
            output.mkdir()
            marker = output / 'prior.txt'
            marker.write_text('prior complete audit')

            with self.assertRaises(FileExistsError):
                self.invoke(repo, output)

            self.assertEqual(marker.read_text(), 'prior complete audit')
            self.assertEqual(
                sorted(path.name for path in output.iterdir()), ['prior.txt'])


if __name__ == '__main__':
    unittest.main()
