#!/usr/bin/env python3
"""Captured-loader receipts bind executed bytes and preserve harness failures."""
import hashlib
import json
import py_compile
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
WRAPPER = HERE / 'pump_with_captured_loader.py'
HARNESS = "from pathlib import Path\nPath(__file__).write_text('# replaced\\n')\n"
LOADER = (
    "from pathlib import Path\n"
    "import hashlib\n"
    "ROOT = Path(__file__).resolve().parents[1]\n"
    "LOADS = []\n"
    "INPUT_SHA256 = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() "
    "for p in (ROOT/'evidence/original/pump').iterdir()}\n"
    "def install():\n"
    "    pass\n"
)


class CapturedLoaderInputHashTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='captured-loader-hashes-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.scripts = self.root / 'scripts'
        self.scripts.mkdir()
        self.wrapper = self.scripts / WRAPPER.name
        shutil.copyfile(WRAPPER, self.wrapper)
        shutil.copyfile(HERE / 'probe_report.py', self.scripts / 'probe_report.py')
        self.loader = self.scripts / 'pump_captured_loader.py'
        self.loader.write_text(LOADER, encoding='utf-8')
        self.evidence = self.root / 'evidence/original/pump'
        self.evidence.mkdir(parents=True)
        for name in ('capture.json', 'program-account.bin', 'programdata-account.bin', 'deployed.so'):
            (self.evidence / name).write_bytes(name.encode())
        self.harness = self.root / 'harness.py'
        self.receipt = self.root / 'receipt.json'

    def run_wrapper(self, harness, *arguments):
        self.harness.write_text(harness, encoding='utf-8')
        return subprocess.run(
            [sys.executable, '-B', str(self.wrapper), '--receipt', str(self.receipt),
             str(self.harness), *map(str, arguments)], text=True, capture_output=True)

    def record(self):
        return json.loads(self.receipt.read_text())

    def test_receipt_keeps_the_hash_of_the_harness_that_ran(self):
        result = self.run_wrapper(HARNESS)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.harness.read_text(), '# replaced\n')
        self.assertEqual(self.record()['input_sha256'][str(self.harness)],
                         hashlib.sha256(HARNESS.encode()).hexdigest())

    def test_install_time_replacement_runs_the_admitted_main_module(self):
        self.loader.write_text(LOADER.replace(
            '    pass\n', "    (ROOT/'harness.py').write_text('raise RuntimeError(\"replacement ran\")\\n')\n"))
        (self.root / 'sibling.py').write_text('VALUE=17\n')
        (self.root / 'payload.txt').write_text('relative input')
        harness = '''from __future__ import annotations
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar
import sibling
@dataclass
class MainProbe:
    value: ClassVar[int] = 17
assert __name__ == '__main__' and __package__ == '' and __spec__ is None
assert sys.modules['__main__'].MainProbe is MainProbe
assert sys.argv == [__file__, 'argument']
assert sibling.VALUE == MainProbe.value
assert Path(__file__).with_name('payload.txt').read_text() == 'relative input'
print('admitted harness ran')
'''
        result = self.run_wrapper(harness, 'argument')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'admitted harness ran')
        self.assertIn('replacement ran', self.harness.read_text())
        self.assertEqual(self.record()['input_sha256'][str(self.harness)],
                         hashlib.sha256(harness.encode()).hexdigest())

    def test_real_loader_records_the_captured_bytes_it_imported(self):
        original = HERE.parent / 'evidence/original/pump'
        for name in ('capture.json', 'program-account.bin', 'programdata-account.bin', 'deployed.so'):
            shutil.copyfile(original / name, self.evidence / name)
        capture = self.evidence / 'capture.json'
        expected = hashlib.sha256(capture.read_bytes()).hexdigest()
        self.loader.write_bytes((HERE / 'pump_captured_loader.py').read_bytes()
                                + b"\n(ROOT/'evidence/original/pump/capture.json').write_bytes(b'changed after import')\n")
        result = self.run_wrapper("import pump_captured_loader as loader\nassert loader.CAPTURE['program']\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(capture.read_bytes(), b'changed after import')
        self.assertEqual(self.record()['input_sha256'][str(capture)], expected)

    def test_real_loader_input_removed_after_import_keeps_its_read_hash(self):
        original = HERE.parent / 'evidence/original/pump'
        for name in ('capture.json', 'program-account.bin', 'programdata-account.bin', 'deployed.so'):
            shutil.copyfile(original / name, self.evidence / name)
        capture = self.evidence / 'capture.json'
        expected = hashlib.sha256(capture.read_bytes()).hexdigest()
        self.loader.write_bytes((HERE / 'pump_captured_loader.py').read_bytes()
                                + b"\n(ROOT/'evidence/original/pump/capture.json').unlink()\n")
        result = self.run_wrapper("import pump_captured_loader as loader\nassert loader.CAPTURE['program']\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(capture.exists())
        self.assertEqual(self.record()['input_sha256'][str(capture)], expected)

    def test_loader_source_hash_describes_the_executed_snapshot(self):
        source = LOADER + "\nPath(__file__).write_text('raise RuntimeError(\"new loader\")\\n')\n"
        self.loader.write_text(source)
        result = self.run_wrapper("print('snapshot loader installed')\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.record()['input_sha256'][str(self.loader)],
                         hashlib.sha256(source.encode()).hexdigest())
        self.assertIn('new loader', self.loader.read_text())

    def test_compiled_harness_keeps_runpy_bytecode_support(self):
        self.harness.write_text("import sys\nassert __file__ == sys.argv[0]\nprint('compiled harness')\n")
        compiled = self.root / 'harness.pyc'
        py_compile.compile(str(self.harness), cfile=str(compiled), doraise=True)
        expected = hashlib.sha256(compiled.read_bytes()).hexdigest()
        result = subprocess.run(
            [sys.executable, '-B', str(self.wrapper), '--receipt', str(self.receipt), str(compiled)],
            text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'compiled harness')
        self.assertEqual(self.record()['input_sha256'][str(compiled)], expected)

    def test_deleted_late_input_does_not_mask_harness_failure(self):
        capture = self.evidence / 'capture.json'
        expected = hashlib.sha256(capture.read_bytes()).hexdigest()
        result = self.run_wrapper(
            f'from pathlib import Path\nPath({str(capture)!r}).unlink()\n'
            "raise RuntimeError('original harness failure')\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('RuntimeError: original harness failure', result.stderr)
        self.assertNotIn('FileNotFoundError', result.stderr)
        self.assertIs(self.record()['ok'], False)
        self.assertEqual(self.record()['input_sha256'][str(capture)], expected)

    def test_receipt_encoding_error_does_not_mask_harness_failure(self):
        self.receipt.write_bytes(b'prior receipt')
        result = self.run_wrapper(
            "import pump_captured_loader as loader\nloader.LOADS.append(object())\n"
            "raise RuntimeError('original harness failure')\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('RuntimeError: original harness failure', result.stderr)
        self.assertNotIn('TypeError', result.stderr)
        self.assertEqual(self.receipt.read_bytes(), b'prior receipt')

    def test_late_receipt_hardlink_does_not_overwrite_captured_input(self):
        capture = self.evidence / 'capture.json'
        expected = capture.read_bytes()
        result = self.run_wrapper(
            f'from pathlib import Path\nPath({str(self.receipt)!r}).hardlink_to(Path({str(capture)!r}))\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(capture.read_bytes(), expected)
        self.assertIs(self.record()['ok'], True)


if __name__ == '__main__':
    unittest.main()
