"""A packet directory that is itself a link must not pass admission.

Sibling of merged #2980, which closed the same gap in
scripts/revalidate_all.py: the manifest-admission checker's payload walk
lstats every entry under the packet root but never the root itself, so a
packet rooted in an external tree passed with the external tree's own
manifest and payloads. The retained batch revalidator (run.py) substitutes
this checker for the frozen one, so the gap reached it too.
"""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check  # noqa: E402


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class ManifestAdmissionPacketRootLinkTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        # An internally consistent packet living outside the packet tree.
        self.external = self.root / 'external-packet'
        self.external.mkdir()
        (self.external / 'data.txt').write_bytes(b'outside bytes\n')
        (self.external / 'manifest.json').write_text(json.dumps(
            {'data.txt': sha256(b'outside bytes\n')}))

    def test_real_packet_directory_passes(self):
        result = check.check_manifest(self.external)
        self.assertEqual(result['status'], 'pass', result)

    def test_symlinked_packet_directory_is_rejected(self):
        link = self.root / 'packet-link'
        link.symlink_to(self.external, target_is_directory=True)
        result = check.check_manifest(link)
        self.assertEqual(result['status'], 'fail', result)
        self.assertTrue(
            any(error.startswith('linked_path') for error in result['errors']),
            result)

    def test_symlinked_payload_still_rejected(self):
        packet = self.root / 'packet'
        packet.mkdir()
        (packet / 'alias').symlink_to(self.external, target_is_directory=True)
        (packet / 'manifest.json').write_text(json.dumps(
            {'alias/data.txt': sha256(b'outside bytes\n')}))
        result = check.check_manifest(packet)
        self.assertEqual(result['status'], 'fail', result)


if __name__ == '__main__':
    unittest.main()
