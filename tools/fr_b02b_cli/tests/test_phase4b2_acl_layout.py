"""Relocation contracts; no real child processes, DLL calls or filesystem writes."""

import ctypes
import importlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from labs.phase4b2_acl import phase4b2_acl_lab as lab
from labs.phase4b2_acl import phase4b2_acl_process as process


TOOL_ROOT = Path(__file__).resolve().parents[1]
LAB_ROOT = TOOL_ROOT / "labs" / "phase4b2_acl"
HARNESS = LAB_ROOT / "phase4b2_acl_harness.py"
PACKAGE = "labs.phase4b2_acl"


class LabLayoutTests(unittest.TestCase):
    def test_package_imports_share_policy_without_native_or_process_start(self):
        with patch.object(ctypes, "WinDLL", create=True) as dll, \
                patch.object(subprocess, "Popen") as start:
            modules = [importlib.import_module(f"{PACKAGE}.phase4b2_acl_{name}")
                       for name in ("harness", "native", "process")]
            for module in modules:
                self.assertEqual(Path(module.__file__).resolve().parent, LAB_ROOT)
                self.assertIs(module.lab, lab)
            dll.assert_not_called()
            start.assert_not_called()

    def test_direct_entry_preserves_plan_and_unapproved_blocks_from_other_cwds(self):
        cases = (([], 0, "PLAN_ONLY"), (["syn01"], 1, "EXECUTION_NOT_APPROVED"),
                 (["syn02"], 1, "EXECUTION_NOT_APPROVED"),
                 (["syn05"], 1, "EXECUTION_NOT_APPROVED"),
                 (["_worker", "hold"], 1, "EXECUTION_NOT_APPROVED"))
        for cwd in (TOOL_ROOT, TOOL_ROOT / "tests", LAB_ROOT):
            for args, expected_exit, expected_code in cases:
                output = io.StringIO()
                with self.subTest(cwd=cwd.name, args=args), \
                        patch.dict(sys.modules), \
                        patch.object(sys, "path", [str(LAB_ROOT), *sys.path]), \
                        patch.object(sys, "argv", [str(HARNESS), *args]), \
                        patch.object(os, "getcwd", return_value=str(cwd)), \
                        patch.object(ctypes, "WinDLL", create=True) as dll, \
                        patch.object(subprocess, "Popen") as start, \
                        redirect_stdout(output):
                    # Emulate the interpreter's script-directory import path;
                    # cwd changes only through a mock, never os.chdir.
                    for name in ("lab", "native", "process"):
                        sys.modules.pop(f"phase4b2_acl_{name}", None)
                    with self.assertRaises(SystemExit) as stopped:
                        runpy.run_path(str(HARNESS), run_name="__main__")
                    self.assertEqual(stopped.exception.code, expected_exit)
                    result = json.loads(output.getvalue())
                    self.assertEqual(result["code"], expected_code)
                    self.assertEqual(result["operational_approval"], "NONE")
                    dll.assert_not_called()
                    start.assert_not_called()

    def test_module_entry_defaults_to_plan_without_native(self):
        output = io.StringIO()
        with patch.dict(sys.modules), \
                patch.object(sys, "argv", ["phase4b2_acl_harness"]), \
                patch.object(ctypes, "WinDLL", create=True) as dll, \
                patch.object(subprocess, "Popen") as start, redirect_stdout(output):
            sys.modules.pop(f"{PACKAGE}.phase4b2_acl_harness", None)
            with self.assertRaises(SystemExit) as stopped:
                runpy.run_module(f"{PACKAGE}.phase4b2_acl_harness",
                                 run_name="__main__", alter_sys=True)
            self.assertEqual(stopped.exception.code, 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "PLAN_ONLY")
            dll.assert_not_called()
            start.assert_not_called()

    def test_direct_worker_dependencies_import_without_native_calls(self):
        with patch.dict(sys.modules), \
                patch.object(sys, "path", [str(LAB_ROOT), *sys.path]), \
                patch.object(ctypes, "WinDLL", create=True) as dll, \
                patch.object(subprocess, "Popen") as start:
            for name in ("lab", "native", "process"):
                sys.modules.pop(f"phase4b2_acl_{name}", None)
            native = importlib.import_module("phase4b2_acl_native")
            worker = importlib.import_module("phase4b2_acl_process")
            self.assertIs(native.lab, worker.lab)
            self.assertEqual(Path(worker.__file__).resolve().parent, LAB_ROOT)
            dll.assert_not_called()
            start.assert_not_called()

    def test_child_command_uses_absolute_sibling_script_for_both_cwds(self):
        for alternate in (False, True):
            native = Mock(allow_changes=True)
            start = Mock(side_effect=OSError("synthetic launch stop"))
            driver = process.Processes(native, approved=True, popen=start)
            with self.subTest(alternate_cwd=alternate), self.assertRaises(OSError):
                driver.spawn("hold", alternate_cwd=alternate)
            command = start.call_args.args[0]
            self.assertEqual(command, [sys.executable, "-B", str(HARNESS),
                                      "_worker", "hold", "--execute-approved-lab"])
            self.assertTrue(Path(command[2]).is_absolute())
            self.assertEqual(start.call_args.kwargs["cwd"],
                             lab.ROOT if alternate else str(LAB_ROOT))
            self.assertEqual(start.call_args.kwargs["creationflags"],
                             subprocess.CREATE_NO_WINDOW)
            native.process_handle.assert_not_called()


if __name__ == "__main__":
    unittest.main()
