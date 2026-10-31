#!/usr/bin/env python3
"""A non-object JSON line in the cargo build log must not crash cache verification."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pump_dependency_cache as cache


def finish(cache_object, log_lines):
    """Drive the real DependencyCache.finish against a synthetic log."""
    work = Path(tempfile.mkdtemp(prefix="dep-cache-finish-"))
    log = work / "build.log"
    log.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    # Satisfy finish()'s context checks without a real build layout.
    cache_object.context = {"manifests": {}}
    cache_object.tools = {}
    cache_object.configs = {}
    cache_object.sources = {}
    published = {}

    def publish(target, build_report):
        published["target"] = target

    cache_object.publish = publish
    cache_object.finish(work / "out", log, work / "build-report.json")
    return published


def make_cache(**overrides):
    """A DependencyCache without running __init__ (which shells out to cargo)."""
    obj = object.__new__(cache.DependencyCache)
    for key, value in dict(sdk=Path("/sdk"), entry=Path("/entry"),
                           workspace=Path("/ws"), package_id="pkg",
                           direct=True,
                           record={"main_command": "cargo build",
                                   "main_freshly_compiled": True}).items():
        setattr(obj, key, value)
    for key, value in overrides.items():
        setattr(obj, key, value)
    return obj


class CargoLogNonDictTests(unittest.TestCase):
    def test_non_object_json_lines_are_skipped_like_noise(self):
        for torn in ('123', 'true', 'null', '"stray"', '[1, 2]'):
            with self.subTest(torn=torn):
                finish(make_cache(), [
                    torn,
                    'not json at all',
                    json.dumps({"reason": "compiler-artifact",
                                "package_id": "pkg", "fresh": False}),
                ])

    def test_artifact_rows_still_count(self):
        # With direct=False the fresh-compilation accounting still runs: a bare
        # JSON scalar must be skipped, the artifact row must still be counted,
        # and the record must be updated from it.
        obj = make_cache(direct=False, record={"main_command": None})
        finish(obj, [
            '42',
            json.dumps({"reason": "compiler-artifact", "package_id": "pkg", "fresh": False}),
            json.dumps({"reason": "build-finished", "success": True}),
        ])
        self.assertEqual(obj.record["main_freshly_compiled"], True)
        self.assertEqual(obj.record["external_rebuilt"], 0)
        self.assertEqual(obj.record["external_fresh"], 0)


if __name__ == '__main__':
    unittest.main()
