"""Actual admin-incentive VM runs retain admitted program and metadata bytes.

Captured programs and explicitly synthetic hash-binding JSON exercise admission.
They do not establish a compiled candidate or an independent clean rebuild.
"""
import gzip
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
SCRIPT = ROOT / 'scripts/pump_admin_token_incentives_differential.py'
ORIGINAL = ROOT / 'evidence/original/pump/deployed.so'
OTHER = ROOT / 'evidence/original/pump_fees/deployed.so'
SOURCES = ('programs/pump/src/incentives.rs', 'programs/pump/src/volume_sync.rs',
           'programs/pump/src/lib.rs', 'programs/pump/Cargo.toml', 'programs/pump/Cargo.lock')
DEPENDENCIES = ('spl_token', 'spl_token_2022', 'associated_token')
DRIVER = r'''
import sys, shutil
from pathlib import Path
scripts, directory, replacement, mode = sys.argv[1:]
sys.path.insert(0, scripts)
import pump_admin_token_incentives_differential as module
module.ROOT = Path(directory)
module.TARGET = module.ROOT / 'original.so'
module.IDL = module.ROOT / 'idl.json'
module.SNAPSHOT = module.ROOT / 'snapshot.json'
module.DEPENDENCIES = {name: module.ROOT / (name + '.so') for name in ('spl_token', 'spl_token_2022', 'associated_token')}
returned = []
def hook(frame, event, arg):
    if event == 'return' and frame.f_code.co_name == 'run' and frame.f_code.co_filename == module.__file__:
        returned.append(1)
        if len(returned) == 2:
            sys.setprofile(None)
            for path in [module.TARGET, module.ROOT / 'candidate.so', *module.DEPENDENCIES.values()]:
                shutil.copyfile(replacement, path)
            for path in module.ROOT.rglob('*'):
                if path.is_file() and path.suffix != '.so':
                    path.write_bytes(b'replaced after first pair')
if mode == 'mutate':
    sys.setprofile(hook)
try:
    module.main(module.ROOT / 'candidate.so', module.ROOT / 'build.json',
                module.ROOT / 'report.json.gz', module.ROOT / 'second.json')
finally:
    sys.setprofile(None)
    if mode == 'mutate' and len(returned) < 2:
        raise RuntimeError('first target/candidate pair did not execute')
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class AdminTokenIncentivesPinnedImageTests(unittest.TestCase):
    def staged_run(self, mode):
        temporary = tempfile.TemporaryDirectory(prefix='admin-incentive-binding-')
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        shutil.copyfile(ORIGINAL, directory / 'original.so')
        shutil.copyfile(OTHER if mode == 'wrong' else ORIGINAL, directory / 'candidate.so')
        shutil.copyfile(ROOT / 'evidence/upstream/pump.json', directory / 'idl.json')
        shutil.copyfile(ROOT / 'research/imported-lab/analysis/pump_fun/config-snapshot.json', directory / 'snapshot.json')
        for name in DEPENDENCIES:
            shutil.copyfile(ROOT / 'evidence/dependencies' / name / 'deployed.so', directory / (name + '.so'))
        for name in SOURCES:
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        binding = {'test_only': 'synthetic admission metadata; not a build or clean-rebuild receipt',
                   'comparison': {'original_sha256': sha(ORIGINAL), 'candidate_sha256': sha(directory / 'candidate.so')},
                   'source_sha256': {'test_only': 'no source compilation claimed'}, 'selected_toolchain': 'v1.44'}
        for name in ('build.json', 'second.json'):
            value = json.loads(json.dumps(binding))
            if mode == 'bad-' + name:
                value['comparison']['candidate_sha256'] = sha(OTHER)
            (directory / name).write_text(json.dumps(value), encoding='utf-8')
        before = {str(path.relative_to(directory)): sha(path) for path in directory.rglob('*') if path.is_file()}
        environment = dict(os.environ)
        environment.pop('PYTHONOPTIMIZE', None)
        result = subprocess.run([sys.executable, '-B', '-c', DRIVER, str(ROOT / 'scripts'),
                                 str(directory), str(OTHER), mode],
                                cwd=ROOT, env=environment, text=True, capture_output=True, timeout=180)
        return result, directory, before

    def test_program_and_receipt_inputs_survive_replacement(self):
        result, directory, before = self.staged_run('mutate')
        self.assertEqual(result.returncode, 0, result.stdout[-2000:] + result.stderr[-2000:])
        for name, digest in before.items():
            self.assertNotEqual(sha(directory / name), digest, name + ' was not mutated')
        report = json.loads(gzip.decompress((directory / 'report.json.gz').read_bytes()))
        for field, name in [('target_sha256', 'original.so'), ('candidate_sha256', 'candidate.so'),
                            ('build_comparison_sha256', 'build.json'), ('idl_sha256', 'idl.json'),
                            ('global_snapshot_sha256', 'snapshot.json')]:
            self.assertEqual(report[field], before[name])
        self.assertEqual(report['second_clean_build']['comparison_sha256'], before['second.json'])
        self.assertEqual(report['source_sha256'], {name: before[name] for name in SOURCES})
        self.assertEqual(report['dependency_sha256'], {name: before[name + '.so'] for name in DEPENDENCIES})
        self.assertGreater(report['summary']['cases'], 1)
        self.assertEqual(report['summary']['cases'], report['summary']['matched'])

    def test_wrong_real_candidate_produces_mismatches(self):
        result, directory, _ = self.staged_run('wrong')
        self.assertEqual(result.returncode, 1, result.stderr[-2000:])
        report = json.loads(gzip.decompress((directory / 'report.json.gz').read_bytes()))
        self.assertEqual(report['candidate_sha256'], sha(OTHER))
        self.assertLess(report['summary']['matched'], report['summary']['cases'])

    def test_bad_primary_and_second_bindings_fail_before_publication(self):
        for name in ('build.json', 'second.json'):
            with self.subTest(binding=name):
                result, directory, _ = self.staged_run('bad-' + name)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('AssertionError', result.stderr)
                self.assertFalse((directory / 'report.json.gz').exists())

    def test_optimized_runs_fail_before_imports(self):
        environment = dict(os.environ)
        environment.pop('PYTHONOPTIMIZE', None)
        for flags, env in ((['-O'], environment), (['-OO'], environment),
                           ([], dict(environment, PYTHONOPTIMIZE='1'))):
            with self.subTest(flags=flags):
                result = subprocess.run([sys.executable, '-B', *flags, str(SCRIPT), '--help'],
                                        cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 1)
                self.assertIn('Normal Python is required', result.stderr)
                self.assertNotIn('usage:', result.stdout)


if __name__ == '__main__':
    unittest.main()
