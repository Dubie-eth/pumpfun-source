"""Synthetic Mayhem CPI assertions must not disappear under optimized Python."""

import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pump_set_mayhem_params_synthetic_cpi.py"
MESSAGE = "Normal Python is required; do not use -O or PYTHONOPTIMIZE."


class SyntheticMayhemParamsNormalPythonTests(unittest.TestCase):
    def assert_rejected(self, arguments, environment):
        result = subprocess.run(
            arguments, cwd=ROOT, env=environment, capture_output=True,
            text=True, timeout=30,
        )
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(MESSAGE, output)
        self.assertNotIn("ModuleNotFoundError", output)

    def test_optimized_interpreter_is_rejected_before_imports(self):
        self.assert_rejected(
            [sys.executable, "-O", str(SCRIPT)], dict(os.environ))

    def test_pythonoptimize_environment_is_rejected_before_imports(self):
        environment = dict(os.environ, PYTHONOPTIMIZE="1")
        self.assert_rejected([sys.executable, str(SCRIPT)], environment)


if __name__ == "__main__":
    unittest.main()
