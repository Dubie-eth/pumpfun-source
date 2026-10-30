#!/usr/bin/env python3
"""A new lifecycle run must not replace a retained report."""

import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lifecycle  # noqa: E402


class OutputRefusalTests(unittest.TestCase):
    def run_over(self, output):
        argv = ["lifecycle.py", "--candidate", "candidate.so", "--output", str(output)]
        with (mock.patch.object(sys, "argv", argv),
              mock.patch.object(lifecycle, "run_suite", side_effect=RuntimeError("cases started")),
              contextlib.redirect_stderr(io.StringIO())):
            try:
                with self.assertRaisesRegex(SystemExit, "refusing to overwrite"):
                    lifecycle.main()
            except RuntimeError as error:
                self.fail(f"{error}: an occupied output was accepted")

    def test_existing_report_is_retained(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "report.json.gz"
            output.write_bytes(b"retained report\n")
            self.run_over(output)
            self.assertEqual(output.read_bytes(), b"retained report\n")

    def test_dangling_output_link_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "report.json.gz"
            os.symlink(Path(temporary) / "elsewhere.json.gz", output)
            self.run_over(output)
            self.assertFalse((Path(temporary) / "elsewhere.json.gz").exists())

    def test_fresh_output_runs_the_suite(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "report.json.gz"
            argv = ["lifecycle.py", "--candidate", "candidate.so", "--output", str(output)]
            with (mock.patch.object(sys, "argv", argv),
                  mock.patch.object(lifecycle, "run_suite", side_effect=RuntimeError("cases started"))):
                with self.assertRaisesRegex(RuntimeError, "cases started"):
                    lifecycle.main()


if __name__ == "__main__":
    unittest.main()
