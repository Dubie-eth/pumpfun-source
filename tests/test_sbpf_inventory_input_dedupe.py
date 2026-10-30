"""The disassembly inventory must admit each captured program exactly once.

``capture_directory`` already routes ``donation_relay`` into
``evidence/dependencies``, and ``main`` then sweeps that same directory for
every dependency binary. On this repository's own evidence layout the selector
therefore offered ``donation_relay`` twice and the preflight refused the whole
run with ``duplicate program output name: 'donation_relay'``, so the tool
could not produce an inventory at all.
"""
import contextlib
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import sbpf_disassembly_inventory as inventory

ELF = bytes(64) + struct.pack('<BBhi', 0x95, 0, 0, 0)  # one `exit` in .text at 64
TEXT_ONLY = {'.text': (0, 1, 6, 64, 64, 8, 0, 0, 8, 0)}


class CapturedInputTests(unittest.TestCase):
    def test_selector_and_dependency_sweep_yield_each_program_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('pump',):
                (root / 'evidence/original' / name).mkdir(parents=True)
                (root / 'evidence/original' / name / 'deployed.so').write_bytes(ELF)
            for name in ('donation_relay', 'spl_token'):
                (root / 'evidence/dependencies' / name).mkdir(parents=True)
                (root / 'evidence/dependencies' / name / 'deployed.so').write_bytes(ELF)
            self.assertEqual(
                [(name, path.relative_to(root)) for name, path in inventory.capture_inputs(root)],
                [('pump', Path('evidence/original/pump/deployed.so')),
                 ('donation_relay', Path('evidence/dependencies/donation_relay/deployed.so')),
                 ('spl_token', Path('evidence/dependencies/spl_token/deployed.so'))],
            )


class InventoryRunTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        for name in ('pump',):
            (self.root / 'evidence/original' / name).mkdir(parents=True)
            (self.root / 'evidence/original' / name / 'deployed.so').write_bytes(ELF)
        for name in ('donation_relay',):
            (self.root / 'evidence/dependencies' / name).mkdir(parents=True)
            (self.root / 'evidence/dependencies' / name / 'deployed.so').write_bytes(ELF)
        self.tool_source = self.root / 'tool'
        executable = self.tool_source / 'target/release/sbpf'
        executable.parent.mkdir(parents=True)
        executable.write_text(
            f'#!{sys.executable}\nimport sys\n'
            "print('sbpf fixture' if '--version' in sys.argv else 'exit')\n")
        executable.chmod(0o700)
        (self.tool_source / 'Cargo.lock').write_text('fixture')
        if shutil.which('git') is None:
            self.skipTest('git is required for the tool-source revision')
        for command in (['init', '-q'], ['add', 'Cargo.lock'],
                        ['-c', 'user.email=t@example.invalid', '-c', 'user.name=t',
                         'commit', '-q', '-m', 'fixture']):
            subprocess.run(['git', '-C', str(self.tool_source), *command], check=True)
        self.output = self.root / 'out/inventory'

    def run_inventory(self):
        argv = ['sbpf_disassembly_inventory', '--tool-source', str(self.tool_source),
                '--output', str(self.output)]
        with patch.object(inventory, 'ROOT', self.root), \
                patch.object(inventory, 'sections', lambda data: TEXT_ONLY), \
                patch.object(sys, 'argv', argv), \
                contextlib.redirect_stdout(io.StringIO()):
            inventory.main()

    def test_run_lists_every_program_once(self):
        self.run_inventory()
        manifest = json.loads((self.output / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual([row['name'] for row in manifest['programs']],
                         ['pump', 'donation_relay'])
        self.assertEqual([row['input'] for row in manifest['programs']],
                         ['evidence/original/pump/deployed.so',
                          'evidence/dependencies/donation_relay/deployed.so'])


if __name__ == '__main__':
    unittest.main()
