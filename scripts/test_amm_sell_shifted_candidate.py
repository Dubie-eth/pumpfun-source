"""A sell size change must not count the moved callees and data as edits.

The candidates are in-memory edits of the captured AMM image, so nothing is
compiled or executed: one instruction goes in at the end of the sell window and
everything after it moves eight bytes, as it does in a real longer build.
"""
import importlib.util
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('shifted_sell_score', HERE / 'amm_sell/sell_score.py')
score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score)

CAPTURE = HERE.parent / 'evidence/original/pump_amm/deployed.so'
INSERTED = struct.pack('<BBhi', 0xbf, 0, 0, 0)  # mov64 r0, r0
SHIFT = len(INSERTED)
START, SIZE = score.SELL_START, score.SELL_SIZE
END = START + SIZE


def lengthened(original):
    """Return the captured image with one more sell instruction and all moves applied."""
    image = bytearray(original.b)
    for row in score.listing(original, START, SIZE):
        at = START + row['off']
        if isinstance(row['target'], tuple) and row['target'][1] >= END:
            immediate = struct.unpack_from('<i', image, at + 4)[0]
            struct.pack_into('<i', image, at + 4, immediate + 1)
        if row['fields'][0] == 'lddw' and at in original.relocations:
            struct.pack_into('<I', image, at + 4, row['fields'][2] + SHIFT)
    secs = {name: section[:3] + (section[3] + SHIFT,) + section[4:]
            for name, section in original.secs.items()}
    secs['.text'] = original.secs['.text']
    return SimpleNamespace(
        b=bytes(image[:END]) + INSERTED + bytes(image[END:]),
        normalized=original.normalized[:END] + INSERTED + original.normalized[END:],
        entries=[at + SHIFT if at >= END else at for at in original.entries],
        hi=original.hi + SHIFT, secs=secs, relocations=dict(original.relocations),
        funcs=[{'name': 'x4sell8cashback', 'start': START, 'size': SIZE + SHIFT}])


def sell_slots(original, kind):
    """Return the offset of the first sell row of one kind."""
    rows = score.listing(original, START, SIZE)
    if kind == 'call':
        return next(START + row['off'] for row in rows
                    if isinstance(row['target'], tuple) and row['target'][1] >= END)
    return next(START + row['off'] for row in rows
                if row['fields'][0] == 'lddw' and START + row['off'] in original.relocations)


class ShiftedCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = score.elf_reader.Elf(CAPTURE)

    def measure(self, candidate):
        original = self.original
        def image(path):
            return original if path == CAPTURE else candidate
        with tempfile.TemporaryDirectory() as out, \
                mock.patch.object(score, 'ORIGINAL', CAPTURE), \
                mock.patch.object(score.elf_reader, 'Elf', side_effect=image):
            return score.score(out)

    def test_one_inserted_instruction_costs_one_edit(self):
        report = self.measure(lengthened(self.original))
        self.assertEqual(report['sell_size'], SIZE + SHIFT)
        self.assertEqual(report['lost_windows_normalized'], [])
        self.assertEqual(report['align_distance'], 1)

    def test_equal_size_capture_stays_at_zero(self):
        candidate = SimpleNamespace(**vars(self.original))
        candidate.funcs = [{'name': 'x4sell8cashback', 'start': START, 'size': SIZE}]
        report = self.measure(candidate)
        self.assertEqual(report['align_distance'], 0)
        self.assertTrue(report['sell_raw_equal'])

    def test_wrong_callee_after_the_shift_still_differs(self):
        candidate = lengthened(self.original)
        image = bytearray(candidate.b)
        at = sell_slots(self.original, 'call')
        immediate = struct.unpack_from('<i', image, at + 4)[0]
        target = at + 8 + immediate * 8
        following = candidate.entries[candidate.entries.index(target) + 1]
        struct.pack_into('<i', image, at + 4, (following - at - 8) // 8)
        candidate.b = bytes(image)
        self.assertEqual(self.measure(candidate)['align_distance'], 2)

    def test_wrong_pointer_after_the_shift_still_differs(self):
        candidate = lengthened(self.original)
        image = bytearray(candidate.b)
        at = sell_slots(self.original, 'lddw')
        value = struct.unpack_from('<I', image, at + 4)[0]
        struct.pack_into('<I', image, at + 4, value + 1)
        candidate.b = bytes(image)
        self.assertEqual(self.measure(candidate)['align_distance'], 2)

    def test_unpaired_windows_keep_their_addresses(self):
        candidate = lengthened(self.original)
        candidate.entries = candidate.entries[:-1]
        report = self.measure(candidate)
        self.assertIsNone(report['lost_windows_normalized'])
        calls = [row for row in score.listing(self.original, START, SIZE)
                 if isinstance(row['target'], tuple) and row['target'][1] >= END]
        self.assertEqual(report['align_distance'], 1 + len(calls))


if __name__ == '__main__':
    unittest.main()
