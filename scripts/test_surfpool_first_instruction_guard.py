#!/usr/bin/env python3
"""The surfpool replay must not blind-overwrite the first recorded instruction.

The replay rebuilt every fixture instruction and then replaced element 0 with
a compute-budget limit without checking what element 0 was. The buy_v2 drivers
skip COMPUTE-targeted instructions explicitly; a fixture whose recorded
transaction did not lead with a compute-budget instruction would have one real
program call silently dropped on both images. The drivers execute at import,
so the invariant is pinned at the source level.
"""
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parent
DRIVERS = (
    "pump_migrate_surfpool.py",
    "pump_migrate_v2_surfpool.py",
    "pump_exact_quote_surfpool.py",
    "pump_holder_distribution_surfpool.py",
    "pump_v3_configured_fee_surfpool.py",
)
GUARD = "assert keys[instructions[0].program_id]==COMPUTE"
OVERWRITE = "instructions[0]=f.set_compute_unit_limit(1400000-len(rows))"


class SurfpoolFirstInstructionGuardTests(unittest.TestCase):
    def test_every_overwrite_is_preceded_by_a_compute_budget_check(self):
        for name in DRIVERS:
            with self.subTest(driver=name):
                source = (SCRIPTS / name).read_text(encoding="utf-8")
                self.assertIn(GUARD, source)
                self.assertLess(source.index(GUARD), source.index(OVERWRITE))
                self.assertIn("COMPUTE=f.Pubkey.from_string('ComputeBudget111111111111111111111111111111')", source)


if __name__ == "__main__":
    unittest.main()
