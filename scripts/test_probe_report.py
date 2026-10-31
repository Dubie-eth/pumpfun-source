#!/usr/bin/env python3
"""Regression tests for durable local probe report output."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_report import write_json_report


class ProbeReportTests(unittest.TestCase):
    def test_long_report_names_leave_room_for_the_staging_suffix(self):
        # Both names fit a 255-byte POSIX component limit; Windows also accepts
        # them. The long-path prefix avoids conflating the Windows total-path
        # limit with the individual filename limit exercised here.
        for name in ('r' * 235 + '.json', '\u00e9' * 117 + '.json'):
            for existing in (False, True):
                with self.subTest(name=name, existing=existing), tempfile.TemporaryDirectory() as tmp:
                    parent = Path(tmp).resolve()
                    if os.name == 'nt':
                        parent = Path('\\\\?\\' + str(parent))
                    report = parent / name
                    if existing:
                        report.write_bytes(b'{"prior": true}\n')
                    value = {"long_name": name, "replaced": existing}

                    write_json_report(report, value)

                    self.assertEqual(json.loads(report.read_text(encoding='utf-8')), value)
                    self.assertEqual(list(parent.glob('.*')), [])

    def test_writes_into_missing_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "new" / "nested" / "report.json"
            value = {"case": "clean checkout", "runs": [1, 2, 3]}

            write_json_report(report, value)

            self.assertEqual(json.loads(report.read_text(encoding="utf-8")), value)
            self.assertTrue(report.read_text(encoding="utf-8").endswith("\n"))

    def test_rewrites_an_existing_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.json"
            report.write_text("old\n", encoding="utf-8")

            write_json_report(report, {"current": True})

            self.assertEqual(
                json.loads(report.read_text(encoding="utf-8")), {"current": True}
            )


if __name__ == "__main__":
    unittest.main()
