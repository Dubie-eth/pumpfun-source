import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_score_pair as pair  # noqa: E402


class BuilderRuntimeErrorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        for path in (self.root / 'sdk/llvm/bin/llvm-objdump', self.root / 'hybrid/rust/bin/rustc'):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'tool fixture')
        canonical = self.root / 'canonical'
        canonical.mkdir()
        for name in ('original.so', 'functions.tsv'):
            (canonical / name).write_bytes(b'input fixture')

    def test_link_receipt_failure_exits_as_a_gate_error_not_a_regression(self):
        failure = RuntimeError('link receipt does not match the pinned link script')
        argv = ['pair', '--base', str(self.root / 'base'), '--candidate', str(self.root / 'candidate'),
                '--out', str(self.root / 'output'), '--sdk', str(self.root / 'sdk'),
                '--hybrid', str(self.root / 'hybrid')]
        stderr = io.StringIO()
        receipt = {'revision': 'fixture', 'files': {}, 'sha256': 'fixture'}
        with patch.object(sys, 'argv', argv), patch.object(pair, 'source_receipt', return_value=receipt), \
             patch.object(pair, 'copy_original_inputs',
                          side_effect=lambda _, target: [(target / name).write_bytes(b'input fixture')
                                                         for name in ('original.so', 'functions.tsv')]), \
             patch.object(pair, 'bound_inputs', return_value={}), \
             patch.object(pair.fastbuild, 'build', side_effect=failure), \
             contextlib.redirect_stderr(stderr):
            try:
                code = pair.main()
            except SystemExit as error:
                code = error.code
            except RuntimeError as error:
                self.fail(f'builder failure escaped the gate as exit status 1: {error}')
        self.assertEqual(code, 2)
        self.assertIn('build/score gate failed', stderr.getvalue())
        saved = json.loads((self.root / 'output/receipt.json').read_text())
        self.assertEqual(saved['error'], str(failure))


if __name__ == '__main__':
    unittest.main()
