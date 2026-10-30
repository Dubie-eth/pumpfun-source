"""Regression tests: verdict publication must not follow a planted link.

evaluate() used to publish verdict.json at its fixed name with a plain
write_text, so a symlink planted at the verdict path redirected the write
into an unrelated file and the published verdict itself stayed a symlink.
Publication now stages through an exclusively created, unpredictable
sibling (the score.write_report pattern) and replaces the destination.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import match_oracle as oracle


class VerdictStagingTests(unittest.TestCase):
    def run_evaluate(self, root, out, work_name='work'):
        for name in ['original.so', 'functions.tsv']:
            (root / name).write_bytes(b'fixture')
        with patch.object(oracle.score, 'BASE', root), \
                patch.object(oracle.score, 'original_windows',
                             return_value=[{'start': 8}]), \
                patch.object(oracle.fastbuild, 'build',
                             return_value={'ok': False}):
            return oracle.evaluate(root, root / work_name, out, 8,
                                   'normalized', 'identity')

    def test_planted_verdict_symlink_is_replaced_not_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); out = root / 'out'; out.mkdir()
            victim = root / 'victim.json'
            victim.write_text('{"sentinel": "do-not-touch"}\n')
            (out / 'verdict.json').symlink_to(victim)
            self.assertEqual(self.run_evaluate(root, out), 2)
            self.assertEqual(victim.read_text(), '{"sentinel": "do-not-touch"}\n',
                             'publication followed the planted verdict symlink')
            verdict = out / 'verdict.json'
            self.assertFalse(verdict.is_symlink(),
                             'published verdict must be a regular file')
            self.assertEqual(json.loads(verdict.read_text())['status'], 'error')

    def test_verdict_still_published_and_replaced_on_rerun(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); out = root / 'out'; out.mkdir()
            self.assertEqual(self.run_evaluate(root, out), 2)
            verdict = out / 'verdict.json'
            self.assertTrue(verdict.is_file() and not verdict.is_symlink())
            self.assertEqual(json.loads(verdict.read_text())['status'], 'error')
            # A second run replaces the previous verdict as before.
            self.assertEqual(self.run_evaluate(root, out, 'work2'), 2)
            self.assertEqual(json.loads(verdict.read_text())['status'], 'error')
            self.assertEqual(list(out.glob('.verdict-*')), [],
                             'no staging files may be left behind')


if __name__ == '__main__':
    unittest.main()
