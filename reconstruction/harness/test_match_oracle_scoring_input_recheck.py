"""A build that rewrites its scoring inputs must not receive a verdict.

Sibling of merged #2997 (integrate.py rechecks its composed source, scoring
baseline and scorer after the build) and merged #2945 (build_score_pair binds
its scoring inputs): match_oracle.py built the candidate and then scored it
with score.score, which re-reads the copied originals from the scoring-inputs
directory on every call, but never rechecked that the build left those copies
untouched. A crate build runs arbitrary build-script code, so a build that
rewrote the copied original.so or functions.tsv could score the candidate
against doctored originals and publish a false pass verdict.

The build and the scorer are stubbed, as in test_match_oracle.py; only the
oracle's own build/score wiring is exercised. The stubbed build rewrites one
copied scoring input, exactly what a hostile build script could do, while the
stubbed scorer would otherwise report a match.
"""

from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
import match_oracle as oracle


class MatchOracleScoringInputRecheckTests(unittest.TestCase):
    def run_oracle(self, root, out, rewrite):
        def build(source, work, output, quiet=True, recipe=None):
            if rewrite:
                (root / 'work' / 'scoring-inputs' / 'functions.tsv').write_bytes(b'doctored')
            return {'ok': True}

        with patch.object(oracle.score, 'BASE', root), \
                patch.object(oracle.score, 'original_windows', return_value=[{'start': 8}]), \
                patch.object(oracle.fastbuild, 'build', side_effect=build), \
                patch.object(oracle.score, 'score', return_value={8: {'normalized': True}}) as scoring:
            code = oracle.evaluate(root, root / 'work', out, 8, 'normalized', 'identity')
        return code, scoring

    def test_build_rewriting_scoring_inputs_is_refused_a_verdict(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            out = root / 'out'
            out.mkdir()
            for name in ['original.so', 'functions.tsv']:
                (root / name).write_bytes(b'fixture')
            code, scoring = self.run_oracle(root, out, rewrite=True)
            self.assertEqual(code, 2)
            self.assertEqual(scoring.call_count, 0)
            verdict = json.loads((out / 'verdict.json').read_text())
            self.assertEqual(verdict['status'], 'error')
            self.assertIn('scoring inputs changed during build', verdict['score_error'])
            # The doctored copy stays visible for recovery; the verdict is the refusal.
            self.assertEqual((root / 'work' / 'scoring-inputs' / 'functions.tsv').read_bytes(),
                             b'doctored')

    def test_untouched_scoring_inputs_still_score(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            out = root / 'out'
            out.mkdir()
            for name in ['original.so', 'functions.tsv']:
                (root / name).write_bytes(b'fixture')
            code, scoring = self.run_oracle(root, out, rewrite=False)
            self.assertEqual(code, 0)
            self.assertEqual(scoring.call_count, 1)
            verdict = json.loads((out / 'verdict.json').read_text())
            self.assertEqual(verdict['status'], 'pass')


if __name__ == '__main__':
    unittest.main()
