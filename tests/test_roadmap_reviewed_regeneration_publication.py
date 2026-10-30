"""A failed regeneration publish must leave no partial packet behind.

The guarded generator refuses an existing output directory, so writing its
files directly into the destination was doubly bad: a write failure (for
example a file-size limit) left a truncated observations file with no
manifest, and a retry at the same destination then failed with
"output already exists". The generator now stages beside the destination
and publishes by rename; failures remove only the private stage.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

try:
    import resource
except ImportError:  # pragma: no cover - non-POSIX hosts
    resource = None

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "reconstruction/diagnostics/roadmap-reviewed-regeneration/generate.py"
ARCHIVE = Path("research/tooling-roadmap-call-classification-20261029")


def limit_file_size():
    resource.setrlimit(resource.RLIMIT_FSIZE, (64, 64))


class ReviewedRegenerationPublicationTests(unittest.TestCase):
    def layout(self, root):
        for relative in [Path("scripts/reconstruction_roadmap.py"), Path("scripts/window_elf_reader.py")]:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        shutil.copytree(ROOT / ARCHIVE, root / ARCHIVE,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for name in ["pump", "pump_amm", "mayhem"]:
            relative = Path(f"evidence/original/{name}/deployed.so")
            target = root / relative
            target.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / relative, target)

    def run_generator(self, root, output, limit=False):
        kwargs = {}
        if limit:
            kwargs["preexec_fn"] = limit_file_size
        return subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(GENERATOR),
             "--repo", str(root), "--output", str(output)],
            cwd=root, capture_output=True, text=True, encoding="utf-8",
            timeout=600, **kwargs)

    def check_complete(self, output):
        self.assertTrue((output / "observations.json").is_file())
        self.assertTrue((output / "inputs.json").is_file())
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(set(manifest), {"observations.json", "inputs.json"})
        for name, digest in manifest.items():
            self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)

    def test_successful_run_publishes_complete_directory(self):
        with tempfile.TemporaryDirectory(prefix="pump-roadmap-publication-") as temporary:
            root = Path(temporary).resolve()
            self.layout(root)
            output = root / "regenerated"
            completed = self.run_generator(root, output)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.check_complete(output)
            leftovers = [p.name for p in root.iterdir()
                         if p.name.startswith(".regenerated.staging-")]
            self.assertEqual(leftovers, [])

    @unittest.skipUnless(resource is not None and hasattr(resource, "RLIMIT_FSIZE")
                         and os.name != "nt", "file-size limits are POSIX-only")
    def test_write_failure_leaves_no_output_and_allows_retry(self):
        with tempfile.TemporaryDirectory(prefix="pump-roadmap-publication-") as temporary:
            root = Path(temporary).resolve()
            self.layout(root)
            output = root / "regenerated"
            failed = self.run_generator(root, output, limit=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertFalse(output.exists())
            leftovers = [p.name for p in root.iterdir()
                         if p.name.startswith(".regenerated.staging-")]
            self.assertEqual(leftovers, [])
            retried = self.run_generator(root, output)
            self.assertEqual(retried.returncode, 0, retried.stdout + retried.stderr)
            self.check_complete(output)


if __name__ == "__main__":
    unittest.main()
