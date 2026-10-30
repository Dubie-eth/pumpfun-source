#!/usr/bin/env python3
"""The constant-product comparison slices its original range from a pinned capture."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parent
SCRIPT = "pump_build_constant_product.py"
END = 0x88908
TOOLCHAIN = "fixture-toolchain"
# The builder freezes its source and compiler bytes before compiling, so the
# fixture needs both. This launcher answers the version probe and then fails, so
# the build log records that the run reached the compiler without publishing.
STUB_RUSTC = """#!/bin/sh
case "$*" in
  *--version*) echo 'rustc 0.0.0-fixture (pinning test stub)'; exit 0 ;;
esac
echo 'stub rustc reached'
exit 1
"""
STUB_MARKER = "stub rustc reached"


def fixture_root(blob, manifest_sha=None):
    """A repository fixture holding the builder, its inputs and a captured pump image."""
    temporary = Path(tempfile.mkdtemp(prefix="constant-product-pin-"))
    (temporary / "scripts").mkdir()
    shutil.copy(SCRIPTS / SCRIPT, temporary / "scripts" / SCRIPT)
    source = temporary / "programs/pump/recovered"
    source.mkdir(parents=True)
    (source / "constant_product.rs").write_bytes(b"// fixture source\n")
    rustc = temporary / TOOLCHAIN / "rust/bin/rustc"
    rustc.parent.mkdir(parents=True)
    rustc.write_text(STUB_RUSTC)
    rustc.chmod(0o755)
    (temporary / "evidence/original/pump").mkdir(parents=True)
    (temporary / "evidence/original/pump/deployed.so").write_bytes(blob)
    sha = manifest_sha or hashlib.sha256(blob).hexdigest()
    (temporary / "evidence/original/pump/capture.json").write_text(
        json.dumps({"payload_sha256": sha}))
    return temporary


def run_builder(root):
    return subprocess.run(
        [sys.executable, str(root / "scripts" / SCRIPT),
         "--toolchain", str(root / TOOLCHAIN), "--output", str(root / "out")],
        capture_output=True, text=True)


class PinnedOriginalTests(unittest.TestCase):
    def test_capture_missing_the_manifest_sha_is_rejected_before_building(self):
        root = fixture_root(bytearray(END), manifest_sha="0" * 64)
        completed = run_builder(root)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("does not match its retained capture manifest", completed.stderr)
        self.assertFalse((root / "out/build.log").exists())

    def test_capture_shorter_than_the_range_is_rejected_before_building(self):
        root = fixture_root(bytearray(END - 8))
        completed = run_builder(root)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("shorter than the pinned original function range", completed.stderr)
        self.assertFalse((root / "out/build.log").exists())
        # The unpinned slice this replaces silently returned 8 bytes short.
        blob = (root / "evidence/original/pump/deployed.so").read_bytes()
        self.assertEqual(len(blob[0x880b0:END]), END - 0x880b0 - 8)

    def test_pinned_capture_proceeds_to_the_build(self):
        blob = bytearray(END)
        blob[0x880b0:0x880b0 + 14] = b"fragment-bytes"
        root = fixture_root(bytes(blob))
        completed = run_builder(root)
        self.assertNotEqual(completed.returncode, 0, 'the failing fixture compiler must fail the build')
        # Pinning passed: the run reaches the compiler launcher instead of
        # refusing the capture. The launcher records its invocation and fails, so
        # no comparison is published.
        self.assertNotIn("retained capture manifest", completed.stderr)
        self.assertNotIn("shorter than", completed.stderr)
        log = root / "out/build.log"
        self.assertTrue(log.is_file())
        self.assertIn(STUB_MARKER, log.read_text())
        self.assertFalse((root / "out/comparison.json").exists())


if __name__ == "__main__":
    unittest.main()
