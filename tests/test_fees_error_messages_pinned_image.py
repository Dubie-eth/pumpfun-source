"""Both error-message families must execute one immutable candidate image."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/fees_error_messages_differential.py"


def sha(data):
    return hashlib.sha256(data).hexdigest()


class FeesErrorMessagesPinnedImageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix="fees-error-messages-pinned-image-")
        self.root = Path(self.temporary.name)
        self.candidate = self.root / "candidate.so"
        self.candidate.write_bytes(b"first candidate image")
        self.output = self.root / "report.json"
        self.candidate_reads = []
        self.pins = []
        self.mutated = False

        test = self

        def pin_program(path):
            data = Path(path).read_bytes()
            descriptor, name = tempfile.mkstemp(
                prefix="pinned-", suffix=".so", dir=test.root)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
            pinned = Path(name)
            test.pins.append(pinned)
            return pinned

        def record_candidate(path):
            if Path(path) == test.original:
                return b"original image"
            data = Path(path).read_bytes()
            test.candidate_reads.append(data)
            if not test.mutated:
                test.candidate.write_bytes(b"replacement candidate image")
                test.mutated = True
            return data

        def configuration_result():
            return {
                "error": "AnchorError",
                "data_hex": "00",
                "lamports": 1,
                "owner": "program",
                "balance_deltas": [0, 0, 0],
                "events": [],
                "inner_instructions": [],
                "logs": [
                    "Program log: Error Code: format. "
                    "Error Number: 6003. Error Message: format."
                ],
            }

        def sharing_result():
            return {
                "error": "AnchorError",
                "before": [],
                "after": [],
                "events": [],
                "inner": [],
                "return": None,
                "logs": [
                    "Program log: Error Code: format. "
                    "Error Number: 6011. Error Message: format."
                ],
            }

        configuration = types.ModuleType("fees_config_differential")

        class ConfigFixture:
            def __init__(self, binary=None):
                self.binary = Path(binary) if binary else None
                self.program_sha256 = "original"

            def run(self, case):
                record_candidate(self.binary)
                return configuration_result()

        configuration.ConfigFixture = ConfigFixture
        configuration.cases = lambda: [{"name": "update_fee_config-count-51"}]

        sharing = types.ModuleType("fees_sharing_update_differential")

        def sharing_run(case, binary=None):
            record_candidate(binary)
            return sharing_result()

        sharing.cases = lambda: [{"name": "new-count-11"}]
        sharing.run = sharing_run

        harness = types.ModuleType("pump_amm_reusable_harness")
        harness.pin_program = pin_program

        with mock.patch.dict(sys.modules, {
                "fees_config_differential": configuration,
                "fees_sharing_update_differential": sharing,
                "pump_amm_reusable_harness": harness,
        }, clear=False):
            spec = importlib.util.spec_from_file_location(
                "fees_error_messages_differential_under_test", SCRIPT)
            self.tool = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.tool)
        self.original = self.root / "original.so"
        self.original.write_bytes(b"original image")
        self.tool.ORIGINAL = self.original

    def tearDown(self):
        self.temporary.cleanup()

    def test_candidate_is_pinned_before_both_families_run(self):
        with mock.patch.object(sys, "argv", [
                "fees_error_messages_differential.py",
                "--candidate", str(self.candidate),
                "--output", str(self.output)]):
            self.tool.main()

        self.assertEqual(
            self.candidate_reads, [b"first candidate image"] * 2,
            "the second family executed bytes from a replaced live path")
        report = json.loads(self.output.read_text())
        self.assertEqual(report["candidate_sha256"],
                         sha(b"first candidate image"))
        self.assertEqual(len(self.pins), 1)


if __name__ == "__main__":
    unittest.main()
