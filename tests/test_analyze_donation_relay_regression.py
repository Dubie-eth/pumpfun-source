import contextlib,importlib.util,io,json,shutil,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import analyze as analysis

class DonationRelayTests(unittest.TestCase):
    def test_real_donation_capture_is_selected_and_analyzed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            shutil.copytree(ROOT/'evidence/dependencies/donation_relay',root/'evidence/dependencies/donation_relay')
            (root/'evidence/upstream').mkdir(parents=True)
            with patch.object(analysis,'ROOT',root),contextlib.redirect_stdout(io.StringIO()):
                self.assertIn('donation_relay',analysis.program_names())
                addresses=analysis.program_addresses()
                self.assertEqual(addresses['donation_relay'],json.loads((root/'evidence/dependencies/donation_relay/capture.json').read_text())['program'])
                analysis.analyze()
            output=json.loads((root/'evidence/binary-analysis.json').read_text())
            self.assertIn('donation_relay',output)
            self.assertEqual(output['donation_relay']['allocation_bytes'],(root/'evidence/dependencies/donation_relay/deployed.so').stat().st_size)


if __name__=='__main__':unittest.main(verbosity=2)
