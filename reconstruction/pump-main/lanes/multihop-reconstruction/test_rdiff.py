"""rdiff.py must locate a candidate's swap_hop through the harness's current symbol reader."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
# dis.py in this folder would otherwise shadow the standard library module unittest imports.
sys.path[:] = [entry for entry in sys.path if Path(entry or '.').resolve() != HERE]

import contextlib  # noqa: E402
import io  # noqa: E402
import runpy  # noqa: E402
import unittest  # noqa: E402
from unittest import mock  # noqa: E402

ROOT = HERE.parents[3]
HARNESS = ROOT / 'reconstruction/harness'
sys.path.insert(0, str(HARNESS))
import score  # noqa: E402
import win  # noqa: E402

ORIGINAL_START = 0x5b3b0


class RangeDiffTests(unittest.TestCase):
    def test_candidate_range_diffs_against_the_original_swap_hop(self):
        start = 0x1000
        functions = [(start, 16, 'pump8swap_hop17h0123456789abcdefE')]
        listings = [{start: 'mov64 r1, r2', start + 8: 'exit'},
                    {ORIGINAL_START: 'mov64 r1, r2', ORIGINAL_START + 8: 'mov64 r3, r4'}]
        stdout = io.StringIO()
        argv = ['rdiff.py', str(HARNESS), 'candidate.so', '0', '10', '0', '10']
        with (mock.patch.object(sys, 'argv', argv), mock.patch.object(sys, 'path', list(sys.path)),
              mock.patch.object(score, 'candidate_functions', return_value=functions),
              mock.patch.object(win, 'objdump_text', side_effect=listings),
              contextlib.redirect_stdout(stdout)):
            try:
                runpy.run_path(str(HERE / 'rdiff.py'), run_name='__main__')
            except AttributeError as error:
                self.fail(str(error))
        rows = stdout.getvalue().splitlines()
        self.assertEqual([row[0] for row in rows], [' ', 'r'])
        self.assertIn('mov64 r3, r4', rows[1])
        self.assertIn('exit', rows[1])


if __name__ == '__main__':
    unittest.main()
