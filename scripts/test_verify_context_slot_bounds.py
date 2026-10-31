"""Evidence slots must be valid unsigned Solana slot numbers."""
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import verify_evidence

ROOT = Path(__file__).resolve().parents[1]

class EvidenceContextSlotTests(unittest.TestCase):
    def test_impossible_slots_fail_for_both_loader_types(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / 'evidence', root / 'evidence')
            with patch.object(verify_evidence, 'ROOT', root), contextlib.redirect_stdout(io.StringIO()):
                verify_evidence.main()
                legacy = root / 'evidence/dependencies/associated_token/capture.json'
                unchanged = legacy.read_bytes()
                boundary = json.loads(unchanged)
                boundary['context_slots'] = [0, 2**64 - 1]
                legacy.write_text(json.dumps(boundary), encoding='utf-8')
                verify_evidence.main()
                legacy.write_bytes(unchanged)
                upgradeable = root / 'evidence/original/pump/capture.json'
                unchanged_upgradeable = upgradeable.read_bytes()
                boundary = json.loads(unchanged_upgradeable)
                boundary['context_slots'] = [boundary['last_deploy_slot'], 2**64 - 1, 2**64 - 1, 2**64 - 1]
                upgradeable.write_text(json.dumps(boundary), encoding='utf-8')
                verify_evidence.main()
                upgradeable.write_bytes(unchanged_upgradeable)
                for relative, bad_values in (
                    ('evidence/dependencies/associated_token/capture.json', [[-2, -1], [2**64, 2**64]]),
                    ('evidence/original/pump/capture.json', [[2**64] * 4]),
                ):
                    path = root / relative
                    original = path.read_bytes()
                    for values in bad_values:
                        with self.subTest(path=relative, slots=values):
                            data = json.loads(original)
                            data['context_slots'] = values
                            path.write_text(json.dumps(data), encoding='utf-8')
                            with self.assertRaises(verify_evidence.EvidenceError):
                                verify_evidence.main()
                    path.write_bytes(original)

if __name__ == '__main__':
    unittest.main()
