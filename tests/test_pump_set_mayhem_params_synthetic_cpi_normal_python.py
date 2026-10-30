"""Synthetic Mayhem CPI assertions must not disappear under optimized Python."""

import ast
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pump_set_mayhem_params_synthetic_cpi.py"
HARNESS = ROOT / "scripts/pump_amm_reusable_harness.py"
MESSAGE = "Normal Python is required; do not use -O or PYTHONOPTIMIZE."


def main_function(tree):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node
    raise AssertionError("main() not found")


def assigns_name(node, name):
    return (
        isinstance(node, (ast.Assign, ast.AnnAssign))
        and any(isinstance(target, ast.Name) and target.id == name
                for target in (
                    node.targets if isinstance(node, ast.Assign) else [node.target]))
    )


def calls_name(node, name):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
    )


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

    def test_candidate_is_pinned_before_repeated_case_execution(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        imported = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "pump_amm_reusable_harness"
            and any(alias.name == "pin_program" for alias in node.names)
            for node in ast.walk(tree)
        )
        self.assertTrue(imported, "script must import pin_program")

        main = main_function(tree)
        pin_index = next(
            index for index, node in enumerate(main.body)
            if assigns_name(node, "candidate_path")
            and any(calls_name(child, "pin_program") for child in ast.walk(node))
        )
        candidate_branch = next(
            node for node in main.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "candidate_path"
        )
        self.assertLess(pin_index, main.body.index(candidate_branch))

        run_calls = [
            node for node in ast.walk(candidate_branch)
            if calls_name(node, "run")
        ]
        self.assertTrue(run_calls)
        self.assertTrue(all(
            call.args
            and isinstance(call.args[0], ast.Name)
            and call.args[0].id == "candidate_path"
            for call in run_calls
        ))

        hashes_pinned_path = any(
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Subscript) for target in node.targets)
            and any(
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == "sha"
                and child.args
                and isinstance(child.args[0], ast.Call)
                and isinstance(child.args[0].func, ast.Attribute)
                and child.args[0].func.attr == "read_bytes"
                and isinstance(child.args[0].func.value, ast.Name)
                and child.args[0].func.value.id == "candidate_path"
                for child in ast.walk(node)
            )
            for node in ast.walk(candidate_branch)
        )
        self.assertTrue(hashes_pinned_path)

    def test_pin_program_returns_one_byte_snapshot(self):
        solders = types.ModuleType("solders")
        solders.__path__ = []
        modules = {
            "solders": solders,
            "solders.account": types.SimpleNamespace(Account=object),
            "solders.pubkey": types.SimpleNamespace(Pubkey=object),
            "pump_amm_admin_differential": types.SimpleNamespace(Harness=object),
        }
        with mock.patch.dict(sys.modules, modules, clear=False):
            spec = importlib.util.spec_from_file_location(
                "pump_amm_reusable_harness_under_test", HARNESS)
            harness = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(harness)

        with tempfile.TemporaryDirectory(prefix="pin-program-") as directory:
            source = Path(directory) / "candidate.so"
            source.write_bytes(b"first image")
            pinned = harness.pin_program(source)
            source.write_bytes(b"replacement image")
            self.assertEqual(pinned.read_bytes(), b"first image")
            self.assertEqual(harness.pin_program(source), pinned)


if __name__ == "__main__":
    unittest.main()
