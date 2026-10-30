#!/usr/bin/env python3
"""The surfpool replay must not blind-overwrite the first recorded instruction.

The replay rebuilt every fixture instruction and then replaced element 0 with
a compute-budget limit without checking what element 0 was. The buy_v2 drivers
skip COMPUTE-targeted instructions explicitly; a fixture whose recorded
transaction did not lead with a compute-budget instruction would have one real
program call silently dropped on both images. The drivers execute at import,
so these tests execute their actual admission and replacement statements
with real solders Instruction objects.
"""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace

from solders.compute_budget import set_compute_unit_limit
from solders.instruction import Instruction
from solders.pubkey import Pubkey


SCRIPTS = Path(__file__).resolve().parent
DRIVERS = (
    "pump_migrate_surfpool.py",
    "pump_migrate_v2_surfpool.py",
    "pump_exact_quote_surfpool.py",
    "pump_holder_distribution_surfpool.py",
    "pump_v3_configured_fee_surfpool.py",
)
COMPUTE = Pubkey.from_string('ComputeBudget111111111111111111111111111111')


def replacement_block(name, optimize):
    tree = ast.parse((SCRIPTS / name).read_text(encoding='utf-8'))
    matches = []
    target = ast.dump(ast.parse('instructions[0] = None').body[0].targets[0])
    for node in ast.walk(tree):
        for _, body in ast.iter_fields(node):
            if not isinstance(body, list):
                continue
            for i, statement in enumerate(body):
                if (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                        and ast.dump(statement.targets[0]) == target):
                    if i == 0:
                        raise AssertionError('replacement has no admission check')
                    matches.append([body[i - 1], statement])
    if len(matches) != 1:
        raise AssertionError(f'expected one replacement in {name}, found {len(matches)}')
    constants = [node for node in tree.body if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == 'COMPUTE'
                         for target in node.targets)]
    if len(constants) != 1:
        raise AssertionError(f'expected one compute-budget program binding in {name}')
    return compile(ast.Module(body=constants + matches[0], type_ignores=[]), name, 'exec', optimize=optimize)


def execute(name, instructions, optimize):
    scope = dict(instructions=instructions, keys=[COMPUTE], COMPUTE=COMPUTE,
                 row={'name': 'fixture'}, rows=[None] * 7,
                 f=SimpleNamespace(Pubkey=Pubkey, set_compute_unit_limit=set_compute_unit_limit))
    exec(replacement_block(name, optimize), scope)


class SurfpoolFirstInstructionGuardTests(unittest.TestCase):
    def test_real_compute_budget_is_replaced_in_place(self):
        for name in DRIVERS:
            for optimize in (0, 1, 2):
                with self.subTest(driver=name, optimize=optimize):
                    tail = Instruction(Pubkey.new_unique(), b'unchanged', [])
                    instructions = [set_compute_unit_limit(1), tail]
                    execute(name, instructions, optimize)
                    self.assertEqual(instructions, [set_compute_unit_limit(1_399_993), tail])

    def test_other_program_is_rejected_without_modifying_transaction(self):
        for name in DRIVERS:
            for optimize in (0, 1, 2):
                with self.subTest(driver=name, optimize=optimize):
                    instructions = [Instruction(Pubkey.new_unique(), b'keep', [])]
                    before = list(instructions)
                    with self.assertRaisesRegex(ValueError, 'fixture'):
                        execute(name, instructions, optimize)
                    self.assertEqual(instructions, before)

    def test_empty_transaction_is_rejected(self):
        for name in DRIVERS:
            for optimize in (0, 1, 2):
                with self.subTest(driver=name, optimize=optimize):
                    with self.assertRaisesRegex(ValueError, 'fixture'):
                        execute(name, [], optimize)


if __name__ == "__main__":
    unittest.main()
