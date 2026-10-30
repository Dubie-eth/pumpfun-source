"""Path-keyed manifest records are a retained format, not a parse failure."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import revalidate_all as runner

REPO = Path(__file__).resolve().parents[1]
RETAINED_PACKET = REPO / 'research/window-attribution-resubmit-20261029'


class PathKeyedManifestTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.packet = Path(folder.name)
        self.payload = self.packet / 'payload.txt'
        self.payload.write_bytes(b'bound bytes\n')
        self.record = {'bytes': 12, 'sha256': hashlib.sha256(b'bound bytes\n').hexdigest()}

    def write_manifest(self, document):
        (self.packet / 'manifest.json').write_text(json.dumps(document), encoding='utf-8')

    def test_retained_packet_passes_its_manifest_check(self):
        result = runner.check_manifest(RETAINED_PACKET)
        self.assertEqual(result['status'], 'pass', result)
        self.assertEqual(result['files_checked'], result['files_expected'])

    def test_path_keyed_records_are_checked(self):
        self.write_manifest({'payload.txt': self.record})
        self.assertEqual(runner.check_manifest(self.packet)['status'], 'pass')

    def test_path_keyed_records_keep_hash_and_size_checks(self):
        self.write_manifest({'payload.txt': {**self.record, 'bytes': 13}})
        self.assertEqual(runner.check_manifest(self.packet)['errors'], ['size_mismatch: payload.txt'])
        self.write_manifest({'payload.txt': {**self.record, 'sha256': 'a' * 64}})
        self.assertEqual(runner.check_manifest(self.packet)['errors'], ['hash_mismatch: payload.txt'])

    def test_a_record_cannot_name_a_different_path_than_its_key(self):
        self.write_manifest({'payload.txt': {**self.record, 'path': 'other.txt'}})
        self.assertEqual(runner.check_manifest(self.packet)['status'], 'manifest_parse_error')

    def test_other_nested_objects_remain_invalid(self):
        for document in ({'metadata': {'version': 1}}, {'payload.txt': {'bytes': 12}},
                         {'payload.txt': {**self.record, 'unsupported': 1}}):
            with self.subTest(document=document), self.assertRaises(ValueError):
                runner.manifest_records(document)


if __name__ == '__main__':
    unittest.main()
