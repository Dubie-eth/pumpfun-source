import contextlib,importlib.util,io,json,shutil,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import reconstruction_roadmap as rr

class FunctionalTests(unittest.TestCase):
    def test_real_capture_phase_one_uses_all_eligible_windows(self):
        with tempfile.TemporaryDirectory() as temporary:
            out=Path(temporary)/'out'
            with contextlib.redirect_stdout(io.StringIO()):rr.generate_roadmap(out)
            expected=0
            for f in out.glob('*-details.json'):
                d=json.loads(f.read_text())
                expected+=sum(not w['name'] and w['size']<=512 and bool(w['likely_callers']) for w in d['window_details'])
            plan=json.loads((out/'reconstruction-plan.json').read_text())
            self.assertGreater(expected,0)
            self.assertEqual(plan['phases'][0]['window_count'],expected)


    def test_bridge_window_joins_both_existing_clusters(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'deployed.so').write_bytes(b'fixture')
            windows=[0,8,16]
            attributes={0:{'likely_callers':[('A',1)]},8:{'likely_callers':[('B',1)]},16:{'likely_callers':[('A',1),('B',1)]}}
            elf=SimpleNamespace(entries=windows,hi=24,funcs=[],calls={},relocations={},b=b'\x95'+bytes(7))
            elf.b*=3
            with patch.object(rr,'REPO',root),patch.object(rr,'PROGRAMS',{'fixture':{'deployed':'deployed.so','frontier_normalized':0,'frontier_raw':0}}),patch.object(rr,'Elf',return_value=elf),patch.object(rr,'trace_handler_attribution',return_value=attributes),patch.object(rr,'analyze_cross_references',return_value={}),contextlib.redirect_stdout(io.StringIO()):
                rr.generate_roadmap(root/'out')
            d=json.loads((root/'out/fixture-details.json').read_text())
            self.assertEqual(len(d['reconstruction_clusters']),1)
            self.assertEqual(d['reconstruction_clusters'][0]['window_count'],3)
            self.assertEqual(d['reconstruction_clusters'][0]['total_bytes'],24)


if __name__=='__main__':unittest.main(verbosity=2)
