#!/usr/bin/env python3
"""Every link inside an authenticated vendor package must count as an undeclared member."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("mayhem_native_linux_vendor_links", HERE / "build_linux.py")
native = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(native)


class VendorFileLinkTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mayhem-vendor-links-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.vendor = self.root / "vendor"
        self.controller = self.root / "controller"
        self.controller.mkdir()
        self.package = self.vendor / "example-1.0.0"
        source = self.package / "src/lib.rs"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"pub fn answer() -> u8 { 42 }\n")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        (self.package / ".cargo-checksum.json").write_text(
            json.dumps({"package": "a" * 64, "files": {"src/lib.rs": digest}})
        )
        records = {"packages": [{"directory": "example-1.0.0", "package_sha256": "a" * 64, "file_count": 1}]}
        (self.controller / "vendor-inputs.json").write_text(json.dumps(records))
        self.expected = native.inspect_vendor(self.vendor, self.controller)["closure_sha256"]

    def assert_rejected(self):
        with self.assertRaisesRegex(ValueError, "vendor file set differs"):
            native.check_vendor(self.vendor, self.controller, self.expected)

    def test_dangling_link_is_rejected(self):
        (self.package / "src/generated.rs").symlink_to("missing.rs")
        self.assert_rejected()

    def test_directory_link_is_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "extra.rs").write_bytes(b"pub const EXTRA: u8 = 1;\n")
        (self.package / "src/extra").symlink_to(outside, target_is_directory=True)
        self.assert_rejected()

    def test_fifo_is_rejected(self):
        os.mkfifo(self.package / "src/pipe")
        self.assert_rejected()

    def test_real_empty_directory_is_still_admitted(self):
        (self.package / "src/empty").mkdir()
        self.assertEqual(native.check_vendor(self.vendor, self.controller, self.expected)["packages"], 1)


if __name__ == "__main__":
    unittest.main()
