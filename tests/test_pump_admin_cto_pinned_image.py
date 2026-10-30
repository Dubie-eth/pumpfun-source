"""Real admin_cto VM runs bind every executable and provenance to admitted bytes."""
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
ORIGINAL = ROOT / 'evidence/original/pump/deployed.so'
OTHER = ROOT / 'evidence/original/mayhem/deployed.so'
IMAGES = tuple('evidence/original/' + name + '/deployed.so' for name in ('pump', 'pump_fees', 'pump_amm')) + tuple(
    'evidence/dependencies/' + name + '/deployed.so' for name in ('spl_token', 'spl_token_2022', 'associated_token'))
DRIVER = r'''
import sys, shutil
from pathlib import Path
scripts, directory, replacement, mode = sys.argv[1:]
sys.path.insert(0, scripts)
import pump_admin_cto_differential as module
module.ROOT = Path(directory)
returned = []
if mode in ('metadata', 'original-only'):
    selected = module.cases()[:2]
    module.cases = lambda: selected

def hook(frame, event, arg):
    if event == 'return' and frame.f_code.co_name == 'run' and frame.f_code.co_filename == module.__file__:
        returned.append(1)
        if len(returned) == 2:
            sys.setprofile(None)
            if mode == 'mutate':
                for path in module.ROOT.rglob('*.so'):
                    shutil.copyfile(replacement, path)
            else:
                (module.ROOT / 'evidence/upstream/pump.json').write_bytes(b'replaced metadata')
if mode in ('mutate', 'metadata'):
    sys.setprofile(hook)
sys.argv = [module.__file__, '--output', str(module.ROOT / 'report.json')]
if mode != 'original-only':
    sys.argv += ['--candidate', str(module.ROOT / 'candidate.so')]
try:
    module.main()
finally:
    sys.setprofile(None)
    if mode in ('mutate', 'metadata') and len(returned) < 2:
        raise RuntimeError('first original/candidate pair never executed')
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class PumpAdminCtoPinnedImageTests(unittest.TestCase):
    def staged_run(self, mode):
        temporary = tempfile.TemporaryDirectory(prefix='pump-admin-cto-binding-')
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        for name in IMAGES:
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, path)
        (directory / 'scripts').symlink_to(ROOT / 'scripts', target_is_directory=True)
        upstream = directory / 'evidence/upstream'
        upstream.mkdir()
        for name in ('pump', 'pump_fees', 'pump_amm'):
            shutil.copyfile(ROOT / 'evidence/upstream' / (name + '.json'), upstream / (name + '.json'))
        candidate = directory / 'candidate.so'
        shutil.copyfile(OTHER if mode == 'wrong' else ORIGINAL, candidate)
        before = {name: sha(directory / name) for name in (*IMAGES, 'candidate.so')}
        environment = dict(os.environ)
        environment.pop('PYTHONOPTIMIZE', None)
        result = subprocess.run([sys.executable, '-B', '-c', DRIVER, str(ROOT / 'scripts'),
                                 str(directory), str(OTHER), mode],
                                cwd=ROOT, env=environment, capture_output=True, text=True, timeout=180)
        return result, directory, before

    def test_all_images_keep_admitted_bytes_after_replacement(self):
        result, directory, before = self.staged_run('mutate')
        self.assertEqual(result.returncode, 0, result.stdout[-2000:] + result.stderr[-2000:])
        report = json.loads((directory / 'report.json').read_text(encoding='utf-8'))
        for name, digest in before.items():
            self.assertNotEqual(sha(directory / name), digest)
            self.assertEqual(report['provenance'][str(directory / name)], digest)
        self.assertEqual(report['original_sha256'], before['evidence/original/pump/deployed.so'])
        self.assertEqual(report['candidate_sha256'], before['candidate.so'])
        self.assertEqual(report['mismatches'], [])
        self.assertGreater(report['case_count'], 1)
        for row in report['cases']:
            self.assertTrue(row['match'])
            for side in ('original', 'candidate'):
                self.assertTrue(row[side]['signatures_verified'])
                self.assertFalse(row[side]['pool_authority_top_level_signer'])

    def test_stable_wrong_candidate_reports_real_mismatches(self):
        result, directory, _ = self.staged_run('wrong')
        self.assertEqual(result.returncode, 1, result.stderr[-2000:])
        report = json.loads((directory / 'report.json').read_text(encoding='utf-8'))
        self.assertEqual(report['candidate_sha256'], sha(OTHER))
        self.assertTrue(report['mismatches'])

    def test_original_only_mode_still_works(self):
        result, directory, _ = self.staged_run('original-only')
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        report = json.loads((directory / 'report.json').read_text(encoding='utf-8'))
        self.assertIsNone(report['candidate_sha256'])
        self.assertEqual(report['mismatches'], [])
        self.assertEqual(report['case_count'], 2)
        self.assertTrue(all(row['candidate'] is None and row['match'] is None for row in report['cases']))

    def test_metadata_drift_rejects_publication(self):
        result, directory, _ = self.staged_run('metadata')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Input changed during run', result.stderr)
        self.assertEqual((directory / 'evidence/upstream/pump.json').read_bytes(), b'replaced metadata')
        self.assertFalse((directory / 'report.json').exists())


if __name__ == '__main__':
    unittest.main()
