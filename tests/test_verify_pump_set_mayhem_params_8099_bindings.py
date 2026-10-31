"""The 8099 Mayhem verifier must refuse evidence whose hash maps bind nothing.

The real ``main()`` runs end to end against a hand-built package, with the
differential replay, the historical event check and the transaction parser
replaced by stub_* modules. A complete valid package prints ``verified``.
"""

import gzip
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SOURCE = "programs/pump/src/mayhem.rs"
QUOTE_INPUT = "evidence/quote/input.json"

DRIVER = r"""
import gzip, json, sys, types
from pathlib import Path
root = Path(sys.argv[1])
receipt_path = root / 'repro/pump/mayhem-synthetic-8099/differential.json.gz'

stub_differential = types.ModuleType('pump_set_mayhem_params_synthetic_cpi')
stub_differential.__file__ = str(root / 'differential.py')
def stub_replay():
    output = Path(sys.argv[sys.argv.index('--output') + 1])
    output.write_bytes(receipt_path.read_bytes())
stub_differential.main = stub_replay
stub_historical = types.ModuleType('verify_pump_set_mayhem_params_synthetic')
stub_historical.assert_account_event = lambda case: None
class StubTransaction:
    @classmethod
    def from_bytes(cls, data):
        return cls()
    def verify_with_results(self):
        return [True]
stub_solders = types.ModuleType('solders')
stub_transaction = types.ModuleType('solders.transaction')
stub_transaction.VersionedTransaction = StubTransaction
sys.modules.update({
    'pump_set_mayhem_params_synthetic_cpi': stub_differential,
    'verify_pump_set_mayhem_params_synthetic': stub_historical,
    'solders': stub_solders, 'solders.transaction': stub_transaction})
import verify_pump_set_mayhem_params_8099 as v
v.ROOT = root
v.PACKAGE = root / 'repro/pump/mayhem-synthetic-8099'
v.main()
"""


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Mayhem8099EmptyMapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.package = self.root / "repro/pump/mayhem-synthetic-8099"
        self.package.mkdir(parents=True)
        for rel, data in {
            SOURCE: b"source-bytes", QUOTE_INPUT: b"quote-input",
            "differential.py": b"",
            "evidence/original/pump/deployed.so": b"original",
        }.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.sources = {SOURCE: sha(b"source-bytes")}
        self.bound_inputs = {QUOTE_INPUT: sha(b"quote-input")}

    def write_package(self, sources, bound_inputs):
        package = self.package
        for name, data in {"candidate.so": b"candidate",
                           "synthetic-caller.so": b"caller",
                           "account-snapshot.json.gz": gzip.compress(b"{}")}.items():
            (package / name).write_bytes(data)
        candidate = sha(b"candidate")
        snapshot = sha((package / "account-snapshot.json.gz").read_bytes())
        logs = {}
        for name in ("build.log.gz", "second-build.log.gz"):
            (package / name).write_bytes(gzip.compress(name.encode()))
            logs[name] = sha(name.encode())
        for name, log in (("build-comparison.json", "build.log.gz"),
                          ("second-build-comparison.json", "second-build.log.gz")):
            (package / name).write_text(json.dumps({
                "source_sha256": sources, "selected_toolchain": "v1.44",
                "comparison": {"candidate_sha256": candidate,
                               "full_byte_equality": False},
                "build_log_sha256": logs[log]}))
        (package / "build-reproducibility.json").write_text(json.dumps({
            "source_base_commit": "80990317bd9c0363e071646b892490886d7bf946",
            "candidate_sha256": candidate, "source_sha256": sources,
            "builds_identical": True,
            "differential_script_sha256": sha(b"")}))
        for name in ("build-attempt.json", "second-build-attempt.json"):
            (package / name).write_text(json.dumps({
                "returncode": 0, "source_unchanged": True,
                "source_sha256": sources}))
        case = {"error": None, "signed_transaction_base64": "",
                "signatures_valid": True}
        cases = [dict(case, error=None if i < 13 else "Err") for i in range(25)]
        (package / "differential.json.gz").write_bytes(gzip.compress(json.dumps({
            "candidate_sha256": candidate, "target_sha256": sha(b"original"),
            "synthetic_caller_sha256": sha(b"caller"), "fixture_sha256": snapshot,
            "cases": cases, "candidate_cases": cases,
            "comparison": [{"equal": {"error": True}}] * 25}).encode()))
        (package / "direct-signer-boundary.json").write_text(json.dumps({
            "snapshot_sha256": snapshot, "outer_sol_vault_signer": False,
            "watched_accounts_unchanged": True}))
        quote = gzip.compress(json.dumps({
            "cases": 507, "mismatches": 0,
            "bound_inputs_sha256": bound_inputs}).encode())
        curve = gzip.compress(json.dumps({
            "case_count": 56, "passed": 56, "candidate_sha256": candidate}).encode())
        (package / "quote-control-regression.json.gz").write_bytes(quote)
        (package / "multi-hop-regression.json.gz").write_bytes(curve)
        (package / "regression-summary.json").write_text(json.dumps({
            "candidate_sha256": candidate,
            "quote_control": {"receipt_sha256": sha(quote)},
            "multi_hop_curve": {"receipt_sha256": sha(curve)}}))

    def run_verifier(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SCRIPTS) + os.pathsep + env.get("PYTHONPATH", "")
        return subprocess.run([sys.executable, "-c", DRIVER, str(self.root)],
                              text=True, capture_output=True, env=env, check=False)

    def assert_rejected(self, message):
        completed = self.run_verifier()
        self.assertNotEqual(completed.returncode, 0, completed.stdout)
        self.assertNotIn('"verified": true', completed.stdout)
        self.assertIn(message, completed.stderr)

    def test_valid_package_verifies(self):
        self.write_package(self.sources, self.bound_inputs)
        completed = self.run_verifier()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('"verified": true', completed.stdout)

    def test_empty_build_source_map_rejected(self):
        self.write_package({}, self.bound_inputs)
        self.assert_rejected("build reproducibility binds no source")

    def test_empty_quote_bound_inputs_rejected(self):
        self.write_package(self.sources, {})
        self.assert_rejected("quote-control regression binds no input")

    def test_tampered_source_hash_rejected(self):
        self.write_package({SOURCE: "0" * 64}, self.bound_inputs)
        self.assert_rejected("AssertionError")

    def test_tampered_quote_input_hash_rejected(self):
        self.write_package(self.sources, {QUOTE_INPUT: "0" * 64})
        self.assert_rejected("AssertionError")


if __name__ == "__main__":
    unittest.main()
