"""The sell symbol lookup must not count closures of the sell function."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('closure_sell_score', HERE / 'amm_sell/sell_score.py')
score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score)

PREFIX = '_ZN8pump_amm12instructions4swap4sell8cashback'
SELL = {'name': PREFIX + '17h0123456789abcdefE', 'start': 0x4c750, 'size': 9024}
CLOSURE = {'name': PREFIX + '28_$u7b$$u7b$closure$u7d$$u7d$17hfedcba9876543210E',
           'start': 0x4eaa0, 'size': 64}
OTHER = {'name': '_ZN8pump_amm12instructions4swap3buy17h0123456789abcdefE',
         'start': 0x1000, 'size': 8}


def lookup(*funcs):
    return score.find_sell(SimpleNamespace(funcs=list(funcs)))


class SellSymbolTests(unittest.TestCase):
    def test_closure_does_not_hide_the_sell_function(self):
        for funcs in ((SELL, CLOSURE), (CLOSURE, SELL), (OTHER, CLOSURE, SELL)):
            with self.subTest(order=[row['start'] for row in funcs]):
                try:
                    found = lookup(*funcs)
                except SystemExit as error:
                    self.fail(f'lookup refused a build with one sell function: {error}')
                self.assertEqual(found, SELL)

    def test_sell_function_alone_is_found(self):
        self.assertEqual(lookup(OTHER, SELL), SELL)

    def test_missing_or_repeated_sell_function_is_still_refused(self):
        repeated = {**SELL, 'name': PREFIX + '17hfedcba9876543210E', 'start': 0x50000}
        for funcs in ((OTHER,), (CLOSURE,), (SELL, repeated)):
            with self.subTest(names=[row['name'][-24:] for row in funcs]):
                with self.assertRaises(SystemExit):
                    lookup(*funcs)


if __name__ == '__main__':
    unittest.main()
