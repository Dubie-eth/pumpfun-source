#!/usr/bin/env python3
"""Regression tests: the qualification audit must reject packet members
that are not regular files.

packet_snapshot() records every member's kind, but audit_packet() only
acted on the manifest entries (#2978) and the verifier (run_verifier's own
admission). A data member could be a symlink to content outside the packet
and the audit still passed: the member's identity record holds only the
link target's path, so the bytes the verifier actually read were not bound
by identity_sha256 — mutating the external file left the packet's identity
unchanged. Non-regular, non-directory members other than the manifest and
the verifier now fail the input check.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location("qualification_audit", HERE / "audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def build_packet(packet, external, linked):
    packet.mkdir(parents=True)
    (packet / "README.md").write_text("packet\n")
    manifest = {"README.md": sha(b"packet\n")}
    (packet / "verify.py").write_text(
        "from pathlib import Path\n"
        "assert Path(__file__).with_name('evidence.txt').read_text() == 'GOOD-EVIDENCE'\n"
        "print('packet verifier ok')\n"
    )
    if linked:
        (packet / "evidence.txt").symlink_to(external)
    else:
        (packet / "evidence.txt").write_text("GOOD-EVIDENCE")
        manifest["evidence.txt"] = sha(b"GOOD-EVIDENCE")
    (packet / "manifest.json").write_text(json.dumps(manifest) + "\n")


class NonFileMemberTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen = audit.load_frozen(ROOT)

    def audit_packet(self, packet):
        row, _ = audit.audit_packet(self.frozen, ROOT, packet, 10.0, 1.0)
        return row

    def test_symlinked_data_member_fails_the_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            external = root / "external-evidence.txt"
            external.write_text("GOOD-EVIDENCE")
            packet = root / "packet"
            build_packet(packet, external, linked=True)
            row = self.audit_packet(packet)
            self.assertEqual(row["overall"], "fail")
            self.assertEqual(row["input_check"]["status"], "fail")
            self.assertTrue(any("evidence.txt" in error
                                for error in row["input_check"]["errors"]))

    def test_fifo_member_fails_the_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            external = root / "external-evidence.txt"
            external.write_text("GOOD-EVIDENCE")
            packet = root / "packet"
            build_packet(packet, external, linked=False)
            os.mkfifo(packet / "blob.fifo")
            row = self.audit_packet(packet)
            self.assertEqual(row["overall"], "fail")
            self.assertEqual(row["input_check"]["status"], "fail")

    def test_regular_packet_still_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            external = root / "external-evidence.txt"
            external.write_text("GOOD-EVIDENCE")
            packet = root / "packet"
            build_packet(packet, external, linked=False)
            row = self.audit_packet(packet)
            self.assertEqual(row["overall"], "pass")


if __name__ == "__main__":
    unittest.main()
