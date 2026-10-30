#!/usr/bin/env python3
"""Qualification evidence archives must not embed the wall clock.

archive() wrote tar.gz with tarfile's 'w:gz', whose gzip header carries the
current time; the archives are hashed into MANIFEST.json, so identical inputs
produced different evidence bytes on every run. The qualification drivers
execute at import, so the function is loaded directly from each source via
ast.
"""
import ast
import gzip
import hashlib
import io
import json
import shutil
import tarfile
import time
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parent
DRIVERS = ("pump_macos_v144_qualification.py", "pump_macos_frontier_qualification.py")


def load_archive_function(name):
    source = (SCRIPTS / name).read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "archive")
    module = {"gzip": gzip, "tarfile": tarfile}
    exec(compile(ast.Module(body=[function], type_ignores=[]), name, "exec"), module)
    return module["archive"]


class QualificationArchiveDeterminismTests(unittest.TestCase):
    def test_repeated_archives_of_the_same_tree_are_byte_identical(self):
        import tempfile

        for name in DRIVERS:
            with self.subTest(driver=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / "source"
                (source / "nested").mkdir(parents=True)
                (source / "a.txt").write_bytes(b"alpha")
                (source / "nested" / "b.bin").write_bytes(b"\x00beta")
                archive = load_archive_function(name)
                first = root / "first.tar.gz"
                second = root / "second.tar.gz"
                archive(first, source)
                time.sleep(1.1)
                archive(second, source)
                self.assertEqual(first.read_bytes(), second.read_bytes())
                self.assertEqual(int.from_bytes(first.read_bytes()[4:8], 'little'), 0)
                decoded = gzip.decompress(first.read_bytes())
                with tarfile.open(fileobj=io.BytesIO(decoded), mode='r:') as archive:
                    self.assertEqual(archive.getnames(), ['a.txt', 'nested/b.bin'])
                    self.assertEqual(archive.extractfile('a.txt').read(), b'alpha')
                    self.assertEqual(archive.extractfile('nested/b.bin').read(), b'\x00beta')

    def test_control_retainer_closes_gzip_and_retains_identical_complete_archives(self):
        import tempfile
        source_text = (SCRIPTS / 'pump_current673_macos_control.py').read_text(encoding='utf-8')
        nodes = [node for node in ast.parse(source_text).body
                 if isinstance(node, ast.FunctionDef) and node.name in {'sha', 'write', 'retain'}]
        self.assertEqual(len(nodes), 3)
        namespace = {'gzip': gzip, 'tarfile': tarfile, 'shutil': shutil,
                     'hashlib': hashlib, 'json': json, 'Path': Path}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'control-retainer', 'exec'), namespace)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build = root / 'build'
            (build / 'source').mkdir(parents=True)
            (build / 'source' / 'input.rs').write_bytes(b'pub fn example() {}\n')
            archives = []
            manifests = []
            for name in ('first', 'second'):
                evidence = root / name
                evidence.mkdir()
                namespace['EVIDENCE'] = evidence
                namespace['retain'](build)
                raw = (evidence / 'compiled-source.tar.gz').read_bytes()
                self.assertEqual(int.from_bytes(raw[4:8], 'little'), 0)
                decoded = gzip.decompress(raw)
                with tarfile.open(fileobj=io.BytesIO(decoded), mode='r:') as archive:
                    self.assertEqual(archive.getnames(), ['input.rs'])
                    self.assertEqual(archive.extractfile('input.rs').read(), b'pub fn example() {}\n')
                archives.append(raw)
                manifests.append((evidence / 'MANIFEST.json').read_bytes())
            self.assertEqual(archives[0], archives[1])
            self.assertEqual(manifests[0], manifests[1])


if __name__ == "__main__":
    unittest.main()
