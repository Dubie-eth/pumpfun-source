#!/usr/bin/env python3
"""Guard archived roadmap regeneration with a fixed reviewed-source digest."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import uuid

ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = 'research/tooling-roadmap-call-classification-20261029/proof.py'
SOURCE = 'scripts/reconstruction_roadmap.py'
# Values come from reviewed repository assets, never the current input bytes.
REVIEWED = {
    SOURCE: '7ff87816fe95ceb4b4f3540a34256a5a906665fc9cbe6ae42852c64c27b75f4e',
    ARCHIVE: '4acff7a33fff43773b730b4518a8beb8685abc683740945f27c9296ab4031800',
}


def admitted_inputs(root):
    bindings = {}
    for relative, expected in REVIEWED.items():
        raw = (root / relative).read_bytes()
        if hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest() != expected:
            raise ValueError(f'unreviewed source: {relative}')
        bindings[relative] = hashlib.sha256(raw).hexdigest()
    return bindings


def generate(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    bindings = admitted_inputs(root)  # Before loading or executing either module.
    if output.exists():
        raise ValueError('output already exists; retain prior results')
    spec = importlib.util.spec_from_file_location('reviewed_call_proof', root / ARCHIVE)
    proof = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proof)
    report = proof.check(root)
    for name in proof.PROGRAMS:
        path = f'evidence/original/{name}/deployed.so'
        bindings[path] = hashlib.sha256((root / path).read_bytes()).hexdigest()
    # Stage beside the destination and publish by rename, so a write failure
    # never leaves a partial packet at the destination: the destination check
    # above would otherwise block a retry at the same path, and the partial
    # directory would masquerade as a result although it has no manifest.
    # The stage is an ordinary mkdir, so it keeps the caller's umask.
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = None
    for _ in range(8):
        candidate = output.parent / ('.' + output.name + '.staging-' + uuid.uuid4().hex)
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        stage = candidate
        break
    if stage is None:
        raise FileExistsError('could not allocate a staging directory')
    try:
        (stage / 'observations.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        (stage / 'inputs.json').write_text(json.dumps(bindings, indent=2) + '\n', encoding='utf-8')
        manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(stage.iterdir())}
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        if output.exists():
            raise ValueError('output already exists; retain prior results')
        stage.rename(output)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return report['totals']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(generate(args.repo, args.output), indent=2))
    except ValueError as error:
        parser.exit(1, str(error) + '\n')
