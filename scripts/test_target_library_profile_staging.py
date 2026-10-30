#!/usr/bin/env python3
"""Regression tests: profile-manifest publication must not follow a planted
staging path.

finish() used to stage the file manifest at the fixed sibling name
``manifest.name + ".tmp"`` with a plain truncating write. A symlink planted
at that path redirected the write into an unrelated file, and the published
manifest itself ended up as that symlink while finish() still reported
``status="verified"`` with the hash read through the link. Publication now
goes through probe_report.write_json_report, which stages at an
unpredictable exclusively-created name.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pump_target_library_profile as profile


class ProfileStagingTests(unittest.TestCase):
    def make_record(self, base):
        native = base / "native"
        prepared = base / "prepared"
        libraries = base / "libraries"
        out = base / "out"
        for directory in (native, prepared, libraries, out):
            directory.mkdir(parents=True, exist_ok=True)
        (native / "rust/bin").mkdir(parents=True)
        (native / "rust/bin/rustc").write_text("native-rustc\n")
        lib_rel = Path("rust/lib/rustlib/sbf-solana-solana/lib")
        (prepared / "rust/bin").mkdir(parents=True)
        (prepared / lib_rel).mkdir(parents=True)
        (prepared / lib_rel / "libcore.rlib").write_text("prepared-libcore\n")
        rustc = prepared / "rust/bin/rustc"
        rustc.write_text(
            "#!/bin/sh\n"
            f'if [ "$2" = "sysroot" ]; then echo "{prepared}/rust"; exit 0; fi\n'
            f'if [ "$2" = "target-libdir" ]; then echo "{prepared}/{lib_rel}"; exit 0; fi\n'
            "exit 1\n"
        )
        rustc.chmod(0o755)
        (libraries / "self-contained").mkdir()
        (libraries / "libfoo.rlib").write_text("libfoo\n")
        spec = base / "spec.json"
        spec.write_text("{}\n")
        manifest = out / "target-library-profile-files.json"
        record = {
            "profile_spec": str(spec),
            "profile_spec_sha256": profile.sha(spec),
            "implementation": str(Path(__file__).resolve().parent
                                  / "pump_target_library_profile.py"),
            "implementation_sha256": profile.sha(
                Path(__file__).resolve().parent
                / "pump_target_library_profile.py"),
            "native_sdk": str(native),
            "prepared_sdk": str(prepared),
            "library_source": str(libraries),
            "file_manifest": str(manifest),
            "cache_context": {
                "target": "sbf-solana-solana",
                "target_libraries": {
                    "libfoo.rlib": profile.sha(libraries / "libfoo.rlib")},
                "native_sdk_manifest_sha256": profile.digest(
                    profile.inventory(native)),
                "prepared_sdk_manifest_sha256": profile.digest(
                    profile.inventory(prepared)),
            },
        }
        return record, manifest

    def test_planted_staging_symlink_cannot_redirect_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            record, manifest = self.make_record(Path(temporary))
            victim = manifest.parent / "victim-report.json"
            victim.write_text('{"sentinel": "do-not-touch"}\n')
            Path(str(manifest) + ".tmp").symlink_to(victim)
            result = profile.finish(dict(record))
            self.assertEqual(result["status"], "verified")
            self.assertEqual(victim.read_text(), '{"sentinel": "do-not-touch"}\n',
                             "publication followed the planted staging symlink")
            self.assertFalse(manifest.is_symlink(),
                             "published manifest must be a regular file")
            self.assertTrue(manifest.is_file())
            self.assertEqual(profile.sha(manifest),
                             result["file_manifest_sha256"])
            contents = json.loads(manifest.read_text())
            self.assertIn("rust/bin/rustc", contents["native"])

    def test_stale_regular_staging_file_does_not_corrupt_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            record, manifest = self.make_record(Path(temporary))
            Path(str(manifest) + ".tmp").write_text(
                '{"native": {"FORGED": {}}, "prepared": {}}\n')
            result = profile.finish(dict(record))
            self.assertEqual(result["status"], "verified")
            self.assertFalse(manifest.is_symlink())
            contents = json.loads(manifest.read_text())
            self.assertNotIn("FORGED", contents["native"])
            self.assertEqual(profile.sha(manifest),
                             result["file_manifest_sha256"])
            self.assertFalse(Path(str(manifest) + ".tmp").exists()
                             and Path(str(manifest) + ".tmp").is_symlink())


if __name__ == "__main__":
    unittest.main()
