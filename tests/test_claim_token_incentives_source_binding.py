"""The claim verifier must refuse evidence whose source maps bind nothing.

This drives the real ``main()`` CLI against a hand-built root with the
differential module stubbed. The check of interest runs before the inherited
regression receipts are read, so the fixture omits that file: reaching it
(``inherited-regressions.json`` missing) proves the source checks passed.
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
BASELINE = "4ffe8bd88761059693e481ae972443c10204f7af"
SOURCE = "programs/pump/src/claim.rs"
MODES = ([], ["-O"], ["-OO"])

DRIVER = r"""
import hashlib, sys, types
from pathlib import Path
root = Path(sys.argv[1])
stub_differential = types.ModuleType('pump_claim_token_incentives_differential')
stub_differential.ROOT = root
stub_differential.sha = lambda data: hashlib.sha256(bytes(data)).hexdigest()
for name, rel in (('BUILD', 'build.json'), ('ORIGINAL', 'original.so'),
                  ('IDL', 'idl.json'), ('FIXTURE', 'fixture.json'),
                  ('OUT', 'receipt.json')):
    setattr(stub_differential, name, root / rel)
stub_differential.__file__ = str(root / 'differential.py')
sys.modules['pump_claim_token_incentives_differential'] = stub_differential
txmod = types.ModuleType('solders.transaction')
txmod.Transaction = object
sys.modules['solders'] = types.ModuleType('solders')
sys.modules['solders.transaction'] = txmod
import pump_claim_token_incentives_verify as v
sys.argv = ['verify', '--candidate', str(root / 'candidate.so')]
v.main()
"""


def sha(data):
    return hashlib.sha256(data).hexdigest()


class ClaimSourceBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        files = {
            "original.so": b"original", "candidate.so": b"candidate",
            "idl.json": b"{}", "fixture.json": b"{}", "differential.py": b"",
            SOURCE: b"source-bytes",
            "evidence/dependencies/spl_token_2022/deployed.so": b"t22",
            "evidence/dependencies/associated_token/deployed.so": b"ata",
        }
        for rel, data in files.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.sources = {SOURCE: sha(b"source-bytes")}
        self.repro_dir = self.root / "repro/pump/claim-token-incentives"
        self.repro_dir.mkdir(parents=True)
        for name in ("build.log.gz", "build-second.log.gz"):
            (self.repro_dir / name).write_bytes(gzip.compress(b"log"))

    def write(self, report_sources, build_sources):
        build = {"source_sha256": build_sources, "build_log_sha256": sha(b"log")}
        (self.root / "build.json").write_text(json.dumps(build))
        second = self.repro_dir / "build-second-comparison.json"
        second.write_text(json.dumps(build))
        (self.repro_dir / "build-reproducibility.json").write_text(json.dumps({
            "build_receipt_sha256": [sha((self.root / "build.json").read_bytes()),
                                     sha(second.read_bytes())],
            "source_sha256": build_sources,
            "candidate_sha256": [sha(b"candidate")] * 2,
            "builds_identical": True, "deployed_byte_match": False,
        }))
        (self.root / "receipt.json").write_text(json.dumps({
            "baseline_commit": BASELINE,
            "target_sha256": sha(b"original"),
            "candidate_sha256": sha(b"candidate"),
            "build_receipt_sha256": sha((self.root / "build.json").read_bytes()),
            "idl_sha256": sha(b"{}"), "fixture_sha256": sha(b"{}"),
            "script_sha256": sha(b""),
            "dependency_sha256": {"spl_token_2022": sha(b"t22"),
                                  "associated_token": sha(b"ata")},
            "source_sha256": report_sources,
        }))

    def run_modes(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SCRIPTS) + os.pathsep + env.get("PYTHONPATH", "")
        return [(optimization or "normal", subprocess.run(
            [sys.executable, *optimization, "-c", DRIVER, str(self.root)],
            text=True, capture_output=True, env=env, check=False))
            for optimization in MODES]

    def assert_rejected(self, message):
        for mode, completed in self.run_modes():
            with self.subTest(optimization=mode):
                self.assertNotEqual(completed.returncode, 0)
                self.assertIn(message, completed.stderr)
                self.assertNotIn("inherited-regressions.json", completed.stderr)

    def test_empty_report_and_build_sources_rejected(self):
        self.write({}, {})
        self.assert_rejected("report binds no source")

    def test_empty_build_sources_rejected(self):
        self.write(self.sources, {})
        self.assert_rejected("build comparison binds no source")

    def test_tampered_source_hash_rejected(self):
        self.write({SOURCE: "0" * 64}, self.sources)
        self.assert_rejected("claim verification failed")

    def test_bound_sources_pass_the_source_checks(self):
        self.write(self.sources, self.sources)
        for mode, completed in self.run_modes():
            with self.subTest(optimization=mode):
                self.assertIn("inherited-regressions.json", completed.stderr)
                self.assertNotIn("binds no source", completed.stderr)


if __name__ == "__main__":
    unittest.main()
