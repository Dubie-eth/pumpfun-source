"""A stale disassembly staging directory must not block a rerun.

Sibling of merged #2994 (the scorer's staging file gained a random suffix
because a leftover receipt from pid reuse must never block or be removed):
scripts/disassemble.py named its staging directory only by output name and
process id, so an interrupted run's leftover directory made a later run
that reused the same pid fail in mkdir although the output itself was
still fresh. Other staging paths in this tree already qualify the pid
with a random token; this one now does too.

The test reproduces the pid-reuse collision deterministically: the
objdump argument is a FIFO, so the child blocks reading it until the test
has planted the stale directory for the child's exact pid and then feeds
it the fake objdump bytes.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "disassemble.py"
FAKE_OBJDUMP = """#!{python}
import os
import sys
if sys.argv[1] == "--version":
    print("fake objdump 1.0")
else:
    print("disassembly of " + os.path.basename(os.getcwd()) + " from " + sys.argv[-1])
"""


class DisassembleStagingUniquenessTests(unittest.TestCase):
    def test_stale_pid_staging_directory_does_not_block_rerun(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fifo = root / "objdump"
            os.mkfifo(fifo)
            output = root / "asm"
            child = subprocess.Popen(
                [sys.executable, "-B", str(SCRIPT), "--objdump", str(fifo),
                 "--output", str(output)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                # The child is blocked reading the FIFO, so its pid is known
                # before it reaches the staging mkdir: plant exactly the
                # leftover an interrupted run with this pid would leave.
                stale = root / f".asm.{child.pid}"
                stale.mkdir()
                with open(fifo, "w", encoding="utf-8") as stream:
                    stream.write(FAKE_OBJDUMP.format(python=sys.executable))
                _, stderr = child.communicate(timeout=120)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.communicate()
            self.assertEqual(child.returncode, 0, stderr)
            self.assertTrue((output / "manifest.json").is_file())
            # The stale directory is another run's leftover, not ours.
            self.assertTrue(stale.is_dir())
            self.assertEqual(list(stale.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
