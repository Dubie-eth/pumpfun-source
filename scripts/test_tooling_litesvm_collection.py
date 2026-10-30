"""Only absent LiteSVM capabilities may skip VM-backed tooling cases."""
import json
from pathlib import Path
import subprocess
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parent
DRIVER = r'''
import importlib.abc, json, runpy, sys, unittest
from pathlib import Path
scripts, mode = Path(sys.argv[1]), sys.argv[2]
sys.path.insert(0, str(scripts))
import solders.solders as native
if mode == 'missing_native':
    if hasattr(native, 'LiteSVM'):
        del native.LiteSVM
elif mode in ('missing_module', 'broken_import', 'missing_dependency'):
    # These modes test the later Python import boundary even on a host whose
    # native wheel lacks the VM. The marker is never instantiated.
    if not hasattr(native, 'LiteSVM'):
        native.LiteSVM = object
    # solders.__init__ may already have imported the Python VM wrapper.
    # Force this probe through the fresh import boundary under test.
    sys.modules.pop('solders.litesvm', None)
    class Failure(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname == 'solders.litesvm':
                if mode == 'broken_import':
                    raise ImportError('injected unrelated import failure', name='other_backend')
                name = 'solders.litesvm' if mode == 'missing_module' else 'other_dependency'
                raise ModuleNotFoundError('injected missing ' + name, name=name)
    sys.meta_path.insert(0, Failure())
namespace = runpy.run_path(str(scripts/'test_tooling.py'), run_name='collection_probe')
names = ('MayhemReceiptAdmissionTests', 'FeesRuntimeImageBindingTests',
         'FeesErrorMessageExitTests', 'FeesErrorMessageOptimizationTests',
         'CaseComparisonReceiptTests')
skipped = {name: bool(getattr(namespace[name], '__unittest_skip__', False)) for name in names}
suite = unittest.TestSuite()
for name in ('FeesErrorMessageOptimizationTests', 'CaseComparisonReceiptTests'):
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(namespace[name]))
result = unittest.TextTestRunner(stream=sys.stderr).run(suite)
if not result.wasSuccessful():
    raise SystemExit(1)
print(json.dumps({'skipped': skipped, 'independent_tests': result.testsRun}))
'''


class ToolingLiteSVMCollectionTests(unittest.TestCase):
    def probe(self, mode):
        return subprocess.run([sys.executable, '-B', '-c', DRIVER, str(SCRIPTS), mode],
                              capture_output=True, text=True, timeout=60)

    def test_available_vm_keeps_all_runtime_cases_enabled(self):
        import solders.solders as native
        if not hasattr(native, 'LiteSVM'):
            self.skipTest('host solders native wheel does not provide LiteSVM')
        result = self.probe('available')
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(any(report['skipped'].values()))
        self.assertGreater(report['independent_tests'], 0)

    def test_missing_vm_skips_only_runtime_cases(self):
        for mode in ('missing_native', 'missing_module'):
            with self.subTest(mode=mode):
                result = self.probe(mode)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report['skipped'], {
                    'MayhemReceiptAdmissionTests': True,
                    'FeesRuntimeImageBindingTests': True,
                    'FeesErrorMessageExitTests': True,
                    'FeesErrorMessageOptimizationTests': False,
                    'CaseComparisonReceiptTests': False,
                })
                self.assertGreater(report['independent_tests'], 0)

    def test_unrelated_import_errors_are_not_converted_to_skips(self):
        for mode, message in (('broken_import', 'injected unrelated import failure'),
                              ('missing_dependency', 'injected missing other_dependency')):
            with self.subTest(mode=mode):
                result = self.probe(mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)


if __name__ == '__main__':
    unittest.main()
