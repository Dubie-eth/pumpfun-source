"""The revalidator must not accept a linked packet root or a dangling verifier."""
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/revalidate_all.py'
SYMLINKS = hasattr(__import__('os'), 'symlink')


class RevalidatorPacketAdmissionTests(unittest.TestCase):
    def fixture(self, root):
        scripts = root / 'scripts'
        scripts.mkdir()
        shutil.copyfile(SCRIPT, scripts / 'revalidate_all.py')
        (root / 'research').mkdir()
        return scripts / 'revalidate_all.py'

    def run_cli(self, root, script):
        audit = root / 'audit'
        result = subprocess.run(
            [sys.executable, '-B', str(script), '--output', str(audit)],
            cwd=root, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return {entry['packet']: entry
                for entry in json.loads((audit / 'results.json').read_text())}

    @unittest.skipUnless(SYMLINKS, 'packet-root links need symlink support')
    def test_linked_packet_root_is_rejected_without_running_its_verifier(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = self.fixture(root)
            external = root / 'external'
            external.mkdir()
            marker = root / 'external-executed'
            (external / 'verify.py').write_text(
                'from pathlib import Path\nPath('+repr(str(marker))+').write_text("executed")\n'
                'print("EXTERNAL-VERIFIER-EXECUTED")\n')
            (root / 'research' / 'linked').symlink_to(external, target_is_directory=True)
            results = self.run_cli(root, script)
            entry = results['linked']
            self.assertEqual(entry['overall'], 'fail')
            self.assertIn('packet root is not a real directory', entry['verify_check']['output'])
            self.assertNotIn('EXTERNAL-VERIFIER-EXECUTED', entry['verify_check']['output'])
            self.assertFalse(marker.exists())

    @unittest.skipUnless(SYMLINKS, 'dangling verifier links need symlink support')
    def test_dangling_verifier_link_is_rejected_not_skipped(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = self.fixture(root)
            packet = root / 'research' / 'packet'
            packet.mkdir()
            (packet / 'verify.py').symlink_to('missing.py')
            (packet / 'data.bin').write_bytes(b'actual manifest payload')
            (packet / 'manifest.json').write_text(json.dumps({'data.bin': hashlib.sha256(b'actual manifest payload').hexdigest()}))
            results = self.run_cli(root, script)
            entry = results['packet']
            self.assertTrue(entry['has_verify'])
            self.assertEqual(entry['overall'], 'fail')
            self.assertEqual(entry['verify_check']['output'], 'verify.py is not a regular file')


    @unittest.skipUnless(SYMLINKS, 'verifier links need symlink support')
    def test_linked_verifier_does_not_execute_external_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary);script = self.fixture(root)
            packet = root/'research/packet';packet.mkdir()
            marker=root/'linked-source-executed';external=root/'outside.py'
            external.write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()\n')
            (packet/'verify.py').symlink_to(external)
            entry=self.run_cli(root,script)['packet']
            self.assertEqual(entry['overall'],'fail')
            self.assertFalse(marker.exists())

    def test_nonregular_verifier_entries_are_not_executed(self):
        for kind in ('directory', 'fifo'):
            if kind == 'fifo' and not hasattr(os, 'mkfifo'):
                continue
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);script=self.fixture(root)
                packet=root/'research/packet';packet.mkdir()
                verifier=packet/'verify.py'
                verifier.mkdir() if kind == 'directory' else os.mkfifo(verifier)
                entry=self.run_cli(root,script)['packet']
                self.assertTrue(entry['has_verify'])
                self.assertEqual(entry['overall'],'fail')
                self.assertEqual(entry['verify_check']['output'],'verify.py is not a regular file')

    def test_real_packet_still_runs_its_verifier(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = self.fixture(root)
            packet = root / 'research' / 'real'
            packet.mkdir()
            (packet / 'verify.py').write_text('print("REAL-VERIFIER-EXECUTED")\n')
            results = self.run_cli(root, script)
            entry = results['real']
            self.assertEqual(entry['overall'], 'pass')
            self.assertIn('REAL-VERIFIER-EXECUTED', entry['verify_check']['output'])


if __name__ == '__main__':
    unittest.main()
