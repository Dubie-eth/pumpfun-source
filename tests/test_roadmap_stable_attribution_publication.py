"""A failed attribution publish must leave no partial packet behind.

The generator refuses an existing output directory, so writing its
packet directly into the destination was doubly bad: a write failure
(for example a file-size limit) left a truncated details file with no
manifest, and a retry at the same destination then failed with
"output already exists". The generator now stages beside the
destination and publishes by rename; failures remove only the private
stage.
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

try:
    import resource
except ImportError:  # pragma: no cover - non-POSIX hosts
    resource = None

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "reconstruction/diagnostics/roadmap-stable-attribution/generate.py"


def limit_file_size():
    resource.setrlimit(resource.RLIMIT_FSIZE, (64, 64))


class StableAttributionPublicationTests(unittest.TestCase):
    def run_generator(self, output, limit=False):
        kwargs = {}
        if limit:
            kwargs["preexec_fn"] = limit_file_size
        return subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(GENERATOR),
             "--repo", str(ROOT), "--output", str(output)],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            timeout=900, **kwargs)

    def check_complete(self, output):
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        self.assertNotIn("manifest.json", manifest)
        self.assertIn("attribution-inputs.json", manifest)
        self.assertIn("pump-details.json", manifest)
        for name, digest in manifest.items():
            self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)

    def staging_leftovers(self, parent, output):
        return [p.name for p in parent.iterdir()
                if p.name.startswith("." + output.name + ".staging-")]

    def test_successful_run_publishes_complete_directory(self):
        with tempfile.TemporaryDirectory(prefix="pump-stable-attribution-publication-") as temporary:
            parent = Path(temporary).resolve()
            output = parent / "attributed"
            completed = self.run_generator(output)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.check_complete(output)
            self.assertEqual(self.staging_leftovers(parent, output), [])

    @unittest.skipUnless(resource is not None and hasattr(resource, "RLIMIT_FSIZE")
                         and os.name != "nt", "file-size limits are POSIX-only")
    def test_write_failure_leaves_no_output_and_allows_retry(self):
        with tempfile.TemporaryDirectory(prefix="pump-stable-attribution-publication-") as temporary:
            parent = Path(temporary).resolve()
            output = parent / "attributed"
            failed = self.run_generator(output, limit=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertFalse(output.exists())
            self.assertEqual(self.staging_leftovers(parent, output), [])
            retried = self.run_generator(output)
            self.assertEqual(retried.returncode, 0, retried.stdout + retried.stderr)
            self.check_complete(output)


if __name__ == "__main__":
    unittest.main()
