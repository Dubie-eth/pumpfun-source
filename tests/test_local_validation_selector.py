"""An archived selector must name at least one program with a usable address.

``program_addresses`` returned ``repro/programs.json`` verbatim, so an empty
object made ``main()`` loop over nothing and publish
``audit/local-validation.json`` with ``"programs": {}`` and exit 0 — a
self-consistent receipt for a run that validated no program at all. A
non-string address only failed later, inside ``Pubkey.from_string``.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import local_validation


class ArchivedSelectorTests(unittest.TestCase):
    def root_with(self, selector):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / 'repro').mkdir()
        (root / 'repro/programs.json').write_text(json.dumps(selector))
        return root

    def test_empty_selector_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'selects no programs'):
            local_validation.program_addresses(self.root_with({}))

    def test_blank_and_non_string_addresses_are_refused(self):
        for selector in ({'pump': ''}, {'pump': 123}, {'pump': None}, {'': 'address'}):
            with self.subTest(selector=selector):
                with self.assertRaises(ValueError):
                    local_validation.program_addresses(self.root_with(selector))

    def test_valid_selector_is_returned_unchanged(self):
        selector = {'pump': 'address-one', 'pump_amm': 'address-two'}
        self.assertEqual(local_validation.program_addresses(self.root_with(selector)),
                         selector)

    def test_capture_fallback_is_unchanged(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / 'evidence/original/pump').mkdir(parents=True)
        (root / 'evidence/original/pump/deployed.so').write_bytes(b'\x7fELF')
        (root / 'evidence/original/pump/capture.json').write_text(
            json.dumps({'program': 'captured-id'}))
        self.assertEqual(local_validation.program_addresses(root),
                         {'pump': 'captured-id'})


if __name__ == '__main__':
    unittest.main()
