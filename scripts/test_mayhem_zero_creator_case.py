#!/usr/bin/env python3
"""The zero-creator case must actually send a zero creator.

The payload builder hardcoded the paying user as the creator field, so the
case named zero-creator-is-rejected exercised nothing beyond the base case
while the published receipt advertised that coverage. The builder now reads
the case's creator like every sibling create harness.
"""
import struct
import sys
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parent))
import pump_create_mayhem_differential as harness  # noqa: E402


def creator_field(payload):
    offset = 8  # discriminator
    for _ in range(3):  # name, symbol, uri
        length = struct.unpack_from('<I', payload, offset)[0]
        offset += 4 + length
    return payload[offset:offset + 32]


class MayhemZeroCreatorTests(unittest.TestCase):
    def run_case_capturing_payload(self, case):
        payloads = []
        original = harness.Transaction.new_signed_with_payer

        def spy(instructions, payer, signers, blockhash):
            for instruction in instructions:
                if instruction.program_id == harness.PROGRAM:
                    payloads.append(bytes(instruction.data))
            return original(instructions, payer, signers, blockhash)

        with mock.patch.object(harness.Transaction, 'new_signed_with_payer', side_effect=spy):
            harness.run(case)
        self.assertTrue(payloads)
        return payloads[-1]

    def test_zero_creator_case_transmits_the_zero_key(self):
        case = {'case': 'zero-creator-is-rejected',
                'creator': '11111111111111111111111111111111',
                'is_mayhem_mode': True}
        self.assertEqual(creator_field(self.run_case_capturing_payload(case)), bytes(32))

    def test_default_case_still_transmits_the_paying_user(self):
        payload = self.run_case_capturing_payload({'case': 'probe'})
        self.assertNotEqual(creator_field(payload), bytes(32))
        self.assertEqual(creator_field(payload), bytes(harness.USER.pubkey()))


if __name__ == '__main__':
    unittest.main()
