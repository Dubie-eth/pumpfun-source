"""The real Fees withdraw CLI must not publish reports over its inputs."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    'scripts/fees_withdraw_differential.py',
    'scripts/fees_admin_differential.py',
    'scripts/pump_differential_output.py',
    'evidence/upstream/pump_fees.json',
    'evidence/original/pump_fees/deployed.so',
    'evidence/dependencies/spl_token/deployed.so',
    'evidence/dependencies/spl_token_2022/deployed.so',
    'evidence/dependencies/associated_token/deployed.so',
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FeesWithdrawOutputInputTests(unittest.TestCase):
    def test_real_cli_refuses_candidate_and_runtime_input_aliases(self):
        # Every file is an independent test-owned copy. A regressed CLI can
        # destroy only this temporary copy, never a captured repository input.
        with tempfile.TemporaryDirectory(prefix='fees-withdraw-output-') as temporary:
            root = Path(temporary) / 'private runtime root'
            for name in FILES:
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, destination)
            candidate = root / 'candidate.so'
            shutil.copyfile(root / 'evidence/original/pump_fees/deployed.so', candidate)
            sources = [candidate, *(root / name for name in FILES)]
            before = {path: sha(path) for path in sources}
            aliases = root / 'aliases'
            aliases.mkdir()
            executed = {'same-path': 0, 'hardlink': 0, 'symlink': 0}
            skipped_symlinks = []
            for index, source in enumerate(sources):
                outputs = [('same-path', source)]
                hard = aliases / f'{index}-hardlink'
                os.link(source, hard)
                outputs.append(('hardlink', hard))
                symbolic = aliases / f'{index}-symlink'
                try:
                    symbolic.symlink_to(source)
                except OSError as error:
                    if os.name != 'nt' or getattr(error, 'winerror', None) != 1314:
                        raise
                    skipped_symlinks.append(str(source.relative_to(root)))
                else:
                    outputs.append(('symlink', symbolic))
                for kind, output in outputs:
                    with self.subTest(input=str(source.relative_to(root)), alias=kind):
                        child = subprocess.run(
                            [sys.executable, '-B', str(root / FILES[0]),
                             '--candidate', str(candidate), '--output', str(output)],
                            cwd=root, capture_output=True, text=True, timeout=45)
                        self.assertNotEqual(child.returncode, 0, child.stdout)
                        self.assertIn('report output aliases an input', child.stderr)
                        self.assertEqual({path: sha(path) for path in sources}, before)
                        self.assertFalse(list(output.parent.glob('.' + output.name[:32] + '.*')))
                        executed[kind] += 1
            self.assertEqual(executed['same-path'], len(sources))
            self.assertEqual(executed['hardlink'], len(sources))
            self.assertEqual(executed['symlink'] + len(skipped_symlinks), len(sources))
            print(json.dumps({'executed_alias_checks': executed,
                              'windows_symlink_privilege_skips': skipped_symlinks}))


if __name__ == '__main__':
    unittest.main()
