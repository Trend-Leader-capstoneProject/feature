"""B42-02: synthetic evidence and a failed process-SID lookup.

The two adapter modules below are test doubles for the planned internal ports,
not production implementations. Loading a fresh CLI namespace lets later module
imports use these doubles without adding a public authentication bypass.
An unreached SID double is a failure, never evidence that AuthZ blocked access.
"""

import io
import json
import runpy
import sys
import tempfile
import types
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from zipfile import ZIP_DEFLATED, ZipFile

import fr_b02b_a1_adapter as a1
import fr_b02b_observation as observation
from test_fr_b02b_a1_adapter import example


class ReviewRegistrationTests(unittest.TestCase):
    def test_unavailable_process_sid_blocks_before_decision_or_store(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "synthetic A1.zip"
            approvals, batch = example()
            with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
                archive.writestr(a1.A1_ZIP_APPROVALS, json.dumps(approvals))
                archive.writestr(a1.A1_ZIP_BATCH, json.dumps(batch))
            snapshot = a1.load_a1_snapshot(archive_path)
            when = datetime(2026, 11, 10, 8, tzinfo=timezone.utc)
            with patch.object(observation, "utc_now", return_value=when):
                saved = observation.record_observation(
                    snapshot, archive_path, root / "observations", when
                )
            record_dir = Path(saved["directory"])

            # Establish valid input independently, without mocking its validators.
            self.assertEqual(observation.verify_observation(archive_path, record_dir), {
                "status": "PASS_LOCAL_INTEGRITY_ONLY",
                "evidence_id": record_dir.name,
                "publish_authorization": "NONE",
            })
            record = json.loads((record_dir / "observation.json").read_bytes())
            self.assertEqual(record["review_result"], "HOLD")
            self.assertEqual(record["publish_authorization"], "NONE")

            def files():
                return {
                    path.relative_to(root).as_posix(): path.read_bytes()
                    for path in root.rglob("*") if path.is_file()
                }

            before = files()
            private_diagnostic = "synthetic-private-SID-provider-diagnostic"
            windows_auth = types.ModuleType("fr_b02b_windows_auth")
            windows_auth.get_current_process_sid = Mock(
                side_effect=OSError(private_diagnostic)
            )
            protected_store = types.ModuleType("fr_b02b_protected_store")
            protected_store.register = Mock(
                side_effect=AssertionError("registration must not be attempted")
            )
            prompt = Mock(side_effect=AssertionError("review must not be prompted"))
            stdout, stderr = io.StringIO(), io.StringIO()
            cli_path = Path(__file__).resolve().parents[1] / "fr_b02b_cli.py"

            with patch.dict(sys.modules, {
                "fr_b02b_windows_auth": windows_auth,
                "fr_b02b_protected_store": protected_store,
            }), patch.object(uuid, "uuid4", wraps=uuid.uuid4) as new_id, \
                    patch("builtins.input", new=prompt), \
                    patch("webbrowser.open", side_effect=AssertionError("no browser")), \
                    patch("socket.create_connection", side_effect=AssertionError("no HTTP")), \
                    redirect_stdout(stdout), redirect_stderr(stderr):
                # No replacement CLI/service or input validator is supplied.
                entrypoint = runpy.run_path(str(cli_path))["run_cli"]
                try:
                    code = entrypoint([
                        "review-register", "--zip", str(archive_path),
                        "--record-dir", str(record_dir),
                    ], input_func=prompt)
                except SystemExit as exc:
                    code = exc.code

            # Check these even when the command/identity boundary is missing.
            prompt.assert_not_called()
            protected_store.register.assert_not_called()
            new_id.assert_not_called()
            self.assertEqual(files(), before)
            after_record = json.loads((record_dir / "observation.json").read_bytes())
            self.assertEqual(after_record["review_result"], "HOLD")
            self.assertEqual(after_record["publish_authorization"], "NONE")
            self.assertEqual(stdout.getvalue(), "")
            self.assertNotIn("REG-OBS-", stdout.getvalue() + stderr.getvalue())
            self.assertNotIn(private_diagnostic, stdout.getvalue() + stderr.getvalue())
            self.assertNotIn(str(root), stdout.getvalue() + stderr.getvalue())

            # Input validation may run before SID lookup; no ordering assertion
            # forbids those read-only checks. The failing SID port must be reached
            # so that a parser/configuration failure cannot masquerade as AuthZ.
            with self.subTest(contract="SID failure exit code"):
                self.assertEqual(code, 1, stderr.getvalue())
            with self.subTest(contract="BLOCKED diagnostic"):
                self.assertTrue(
                    stderr.getvalue().startswith("BLOCKED: "), stderr.getvalue()
                )
                self.assertEqual(
                    stderr.getvalue(), "BLOCKED: reviewer identity unavailable\n"
                )
            with self.subTest(contract="SID failure actually injected"):
                windows_auth.get_current_process_sid.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
