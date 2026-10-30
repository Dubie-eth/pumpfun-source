"""Do not re-resolve a tool alias after its old target has been fingerprinted."""
import os
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import experiment_runner as runner


class ExecutableSnapshotTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='experiment-tool-snapshot-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'input').write_text('unchanged source\n')

    def swap(self, alias, target):
        replacement = alias.with_name(alias.name + '.next')
        replacement.symlink_to(target)
        replacement.replace(alias)

    def run_during_tool_switch(self, alias, new_target, args):
        real_identity = runner.identity

        def switch_after_admission(*values, **kwargs):
            admitted = real_identity(*values, **kwargs)
            self.swap(alias, new_target)
            return admitted

        with patch.object(runner, 'identity', switch_after_admission):
            return runner.run_trial(self.source, [str(alias), *args], self.root / 'trial')

    @unittest.skipUnless(shutil.which('false'), 'requires a native false executable')
    def test_tool_switch_cannot_cache_a_pass_for_the_old_failing_command(self):
        old = Path(shutil.which('false'))
        alias = self.root / 'false'
        alias.symlink_to(old)
        args = ['-c', 'print("a different real executable ran")']
        self.assertEqual(subprocess.run([str(alias), *args], capture_output=True).returncode, 1)
        first = self.run_during_tool_switch(alias, Path(sys.executable).resolve(), args)
        self.swap(alias, old)
        cached = runner.run_trial(self.source, [str(alias), *args], self.root / 'trial')
        self.assertEqual(first['status'], 'fail', 'a different executable produced a cached pass')
        self.assertTrue(cached['reused'])
        self.assertEqual(cached['status'], 'fail')
        self.assertIn(str(old.resolve()), first['inputs']['inputs'])
        self.assertEqual(first['inputs']['executable'], str(old.resolve()))

    def test_environment_change_cannot_produce_a_cached_result_for_old_environment(self):
        variable = 'PUMP_EXPERIMENT_TEST_VALUE'
        command = [sys.executable, '-c',
                   f'import os; raise SystemExit(0 if os.environ.get({variable!r}) == "old" else 1)']
        real_identity = runner.identity

        def change_after_admission(*values, **kwargs):
            admitted = real_identity(*values, **kwargs)
            os.environ[variable] = 'new'
            return admitted

        with patch.dict(os.environ, {variable: 'old'}):
            with patch.object(runner, 'identity', change_after_admission):
                first = runner.run_trial(self.source, command, self.root / 'trial')
            os.environ[variable] = 'old'
            cached = runner.run_trial(self.source, command, self.root / 'trial')
        self.assertEqual(first['status'], 'pass', 'child used a different environment than its receipt')
        self.assertTrue(cached['reused'])
        self.assertEqual(cached['status'], 'pass')

    def test_caller_command_mutation_cannot_change_admitted_arguments(self):
        admitted_code = 'print("admitted arguments"); raise SystemExit(0)'
        command = [sys.executable, '-c', admitted_code]
        real_copy = runner.shutil.copytree

        def mutate_after_staging(*values, **kwargs):
            copied = real_copy(*values, **kwargs)
            command[-1] = 'print("different arguments"); raise SystemExit(1)'
            return copied

        with patch.object(runner.shutil, 'copytree', mutate_after_staging):
            first = runner.run_trial(self.source, command, self.root / 'trial')
        command[-1] = admitted_code
        cached = runner.run_trial(self.source, command, self.root / 'trial')
        self.assertEqual(first['key'], runner.digest(json.dumps(first['inputs'], sort_keys=True).encode()),
                         'stored admission changed after its cache key was computed')
        self.assertEqual(first['status'], 'pass')
        self.assertTrue(cached['reused'])
        log = self.root / 'trial' / first['attempt'] / 'stdout.log'
        self.assertEqual(log.read_bytes(), b'admitted arguments\n')

    @unittest.skipUnless(os.environ.get('PUMP_BUILD_TEST_SDK') and shutil.which('rustc'),
                         'requires the explicit SBF SDK and a host rustc')
    def test_real_rustc_probe_executes_the_compiler_it_hashed(self):
        sdk = Path(os.environ['PUMP_BUILD_TEST_SDK']).resolve() / 'rust/bin/rustc'
        host = Path(shutil.which('rustc'))
        old = subprocess.check_output([str(sdk), '--version'], cwd=self.root)
        new = subprocess.check_output([str(host), '--version'], cwd=self.root)
        if old == new:
            self.skipTest('host and SDK rustc versions are identical')
        alias = self.root / 'rustc'
        alias.symlink_to(sdk)
        first = self.run_during_tool_switch(alias, host, ['--version'])
        self.swap(alias, sdk)
        cached = runner.run_trial(self.source, [str(alias), '--version'], self.root / 'trial')
        log = self.root / 'trial' / first['attempt'] / 'stdout.log'
        self.assertEqual(log.read_bytes(), old, 'receipt hashed SDK rustc but executed host rustc')
        self.assertTrue(cached['reused'])
        self.assertEqual(first['inputs']['executable'], str(sdk.resolve()))


if __name__ == '__main__':
    unittest.main()
