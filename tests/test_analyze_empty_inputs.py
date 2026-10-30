#!/usr/bin/env python3
"""analyze.py must refuse to publish empty reports for an empty evidence tree."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import analyze  # noqa: E402


class AnalyzeEmptyInputTests(unittest.TestCase):
    def run_analyze(self, root):
        with mock.patch.object(analyze, 'ROOT', root):
            analyze.analyze()
        return root / 'evidence'

    def test_missing_captures_and_idls_publish_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'evidence/upstream').mkdir(parents=True)
            with self.assertRaisesRegex(SystemExit, 'refusing to publish empty reports'):
                self.run_analyze(root)
            self.assertFalse((root / 'evidence/binary-analysis.json').exists())
            self.assertFalse((root / 'evidence/interface-inventory.json').exists())

    def test_captures_without_idls_publish_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capture = root / 'evidence/original/pump'
            capture.mkdir(parents=True)
            for name in ('deployed.so', 'capture.json'):
                shutil.copyfile(ROOT / 'evidence/original/pump' / name, capture / name)
            (root / 'evidence/upstream').mkdir()
            with self.assertRaisesRegex(SystemExit, 'refusing to publish empty reports'):
                self.run_analyze(root)
            self.assertFalse((root / 'evidence/binary-analysis.json').exists())

    def test_captures_and_idls_publish_both_reports(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capture = root / 'evidence/original/pump'
            capture.mkdir(parents=True)
            for name in ('deployed.so', 'capture.json'):
                shutil.copyfile(ROOT / 'evidence/original/pump' / name, capture / name)
            upstream = root / 'evidence/upstream'
            upstream.mkdir()
            shutil.copyfile(ROOT / 'evidence/upstream/pump.json', upstream / 'pump.json')
            evidence = self.run_analyze(root)
            binary = json.loads((evidence / 'binary-analysis.json').read_text())
            inventory = json.loads((evidence / 'interface-inventory.json').read_text())
            self.assertEqual(sorted(binary), ['pump'])
            self.assertEqual(sorted(inventory), ['pump'])


if __name__ == '__main__':
    unittest.main()
