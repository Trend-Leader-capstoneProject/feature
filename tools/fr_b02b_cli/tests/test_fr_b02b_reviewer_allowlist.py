"""B42-02 authorization with synthetic files and explicit protection doubles.

These tests do not provision or certify an operational ACL/configuration.
"""

import io
import json
import sys
import tempfile
import types
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from zipfile import ZipFile

import fr_b02b_a1_adapter as a1
import fr_b02b_observation as observation
import fr_b02b_reviewer_allowlist as allowlist
import fr_b02b_review_service as service
import fr_b02b_windows_auth as windows_auth
from fr_b02b_cli import run_cli
from test_fr_b02b_a1_adapter import example

SID = "S-1-5-21-100-200-300-1001"
OTHER_SID = "S-1-5-21-100-200-300-1002"
ROLE = "EVIDENCE_REVIEWER"


def document(*, sid=SID, active=True):
    return {"schema": "FR_B02B_REVIEWER_ALLOWLIST_V1", "reviewers": [
        {"sid": sid, "active": active, "role": ROLE},
    ]}


class ReviewerAllowlistTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "synthetic-reviewers.json"
        self.write(document())
        self.protection = Mock(return_value=True)
        self.source = allowlist.AllowlistSource(self.path, self.protection)

    def write(self, value):
        self.path.write_text(json.dumps(value), encoding="utf-8")

    def test_verified_active_sid_passes_without_changing_file(self):
        before = self.path.read_bytes()
        self.assertEqual(allowlist.require_authorized_sid(SID, self.source), SID)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertTrue(self.protection.called)

    def test_windows_path_handle_ctime_difference_is_not_a_content_change(self):
        # Reproduce the observed Windows path/fstat difference deterministically.
        original = allowlist.os.fstat

        def different_ctime(fd):
            info = original(fd)
            return types.SimpleNamespace(**{
                key: getattr(info, key) for key in (
                    "st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns",
                )
            }, st_ctime_ns=info.st_ctime_ns + 1)

        with patch.object(allowlist.os, "fstat", side_effect=different_ctime):
            self.assertEqual(allowlist.require_authorized_sid(SID, self.source), SID)

    def test_unlisted_and_inactive_sids_block_even_when_username_matches(self):
        for value in (document(sid=OTHER_SID), document(active=False)):
            with self.subTest(value=value), patch.dict("os.environ", {"USERNAME": OTHER_SID}):
                self.write(value)
                with self.assertRaisesRegex(allowlist.AllowlistError,
                                            "^reviewer is not authorized$"):
                    allowlist.require_authorized_sid(SID, self.source)

    def test_missing_unreadable_and_corrupt_files_block(self):
        self.path.unlink()
        with self.assertRaisesRegex(allowlist.AllowlistError, "^reviewer allowlist unavailable$"):
            allowlist.require_authorized_sid(SID, self.source)
        self.write(document())
        with patch.object(Path, "open", side_effect=PermissionError("private-path")):
            with self.assertRaisesRegex(allowlist.AllowlistError,
                                        "^reviewer allowlist unavailable$"):
                allowlist.require_authorized_sid(SID, self.source)

        bad_records = [
            b"invalid JSON", b"\xff", b"[]", b'{"schema":0,"schema":1}',
            json.dumps({**document(), "extra": 1}).encode(),
            json.dumps({**document(), "schema": "wrong"}).encode(),
            json.dumps({"schema": document()["schema"], "reviewers": [None]}).encode(),
            json.dumps(document(active=1)).encode(),
            json.dumps(document(sid="not-a-SID")).encode(),
            json.dumps({"schema": document()["schema"], "reviewers": [
                {"sid": SID, "active": True, "role": "ADMIN"},
            ]}).encode(),
            json.dumps({"schema": document()["schema"], "reviewers":
                        document()["reviewers"] * 2}).encode(),
            b" " * 65_537,
        ]
        for raw in bad_records:
            with self.subTest(length=len(raw), prefix=raw[:20]):
                self.path.write_bytes(raw)
                with self.assertRaisesRegex(allowlist.AllowlistError,
                                            "^invalid reviewer allowlist$"):
                    allowlist.require_authorized_sid(SID, self.source)

    def test_failed_or_indeterminate_protection_never_reads_the_file(self):
        for result in (False, None, 1, OSError("private-ACL-diagnostic")):
            with self.subTest(result=type(result).__name__):
                self.protection.reset_mock(side_effect=True)
                if isinstance(result, Exception):
                    self.protection.side_effect = result
                else:
                    self.protection.return_value = result
                with patch.object(Path, "open") as opened:
                    with self.assertRaisesRegex(allowlist.AllowlistError,
                                                "^reviewer allowlist protection failure$"):
                        allowlist.require_authorized_sid(SID, self.source)
                    opened.assert_not_called()

    def test_changed_file_or_protection_during_read_blocks(self):
        for change in ("file", "protection"):
            with self.subTest(change=change):
                self.write(document())
                calls = []

                def protection(_path):
                    calls.append(True)
                    if len(calls) == 2:
                        if change == "protection":
                            return False
                        self.path.write_bytes(b"{}")
                    return True

                source = allowlist.AllowlistSource(self.path, protection)
                with self.assertRaises(allowlist.AllowlistError):
                    allowlist.require_authorized_sid(SID, source)
                self.assertEqual(len(calls), 2)

    def test_no_operational_source_is_fail_closed(self):
        with patch.object(Path, "open") as opened:
            with self.assertRaises(allowlist.AllowlistNotConfigured):
                allowlist.require_authorized_sid(SID)
            opened.assert_not_called()

    def test_programming_errors_in_protection_or_configuration_are_not_hidden(self):
        for error_type in (TypeError, AssertionError, RuntimeError):
            for boundary in ("protection", "configuration"):
                with self.subTest(error=error_type.__name__, boundary=boundary):
                    if boundary == "protection":
                        source = allowlist.AllowlistSource(
                            self.path, Mock(side_effect=error_type("synthetic bug"))
                        )
                        with self.assertRaises(error_type):
                            allowlist.require_authorized_sid(SID, source)
                    else:
                        with patch.object(allowlist, "managed_allowlist_source",
                                          side_effect=error_type("synthetic bug")):
                            with self.assertRaises(error_type):
                                allowlist.require_authorized_sid(SID)

    def test_cli_does_not_expose_sid_path_or_protection_bypass_options(self):
        for option in ("--sid", "--allowlist", "--skip-acl"):
            with self.subTest(option=option), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as stopped:
                    run_cli(["review-register", "--zip", "synthetic.zip",
                             "--record-dir", "synthetic-record", option, "synthetic"])
                self.assertEqual(stopped.exception.code, 2)

    def test_cli_failures_have_no_prompt_registration_or_source_mutation(self):
        archive_path = self.root / "synthetic.zip"
        approvals, batch = example()
        with ZipFile(archive_path, "w") as archive:
            archive.writestr(a1.A1_ZIP_APPROVALS, json.dumps(approvals))
            archive.writestr(a1.A1_ZIP_BATCH, json.dumps(batch))
        snapshot = a1.load_a1_snapshot(archive_path)
        when = datetime(2026, 11, 10, 8, tzinfo=timezone.utc)
        with patch.object(observation, "utc_now", return_value=when):
            saved = observation.record_observation(snapshot, archive_path,
                                                   self.root / "observations", when)
        folder = Path(saved["directory"])
        original = {p: p.read_bytes() for p in (
            archive_path, folder / "observation.json", folder / "index.json",
        )}
        prepare = service.prepare_review
        for mode, category, eligible in (
            ("allowed", "protected review registration is not configured", True),
            ("unlisted", "reviewer is not authorized", False),
            ("inactive", "reviewer is not authorized", False),
            ("missing", "reviewer allowlist unavailable", False),
            ("damaged", "invalid reviewer allowlist", False),
            ("ACL", "reviewer allowlist protection failure", False),
            ("ACL-error", "reviewer allowlist protection failure", False),
            ("unconfigured", "protected review registration is not configured", False),
            ("configuration-error", "reviewer allowlist unavailable", False),
        ):
            with self.subTest(mode=mode):
                self.write(document(sid=OTHER_SID if mode == "unlisted" else SID,
                                    active=mode != "inactive"))
                if mode == "missing":
                    self.path.unlink()
                elif mode == "damaged":
                    self.path.write_bytes(b"invalid JSON")
                verifier = Mock(return_value=mode != "ACL")
                if mode == "ACL-error":
                    verifier.side_effect = OSError("private-ACL-error")
                source = allowlist.AllowlistSource(self.path, verifier)
                next_stage = []

                def prepare_and_track(*args, **kwargs):
                    identity = prepare(*args, **kwargs)
                    next_stage.append(identity)
                    return identity

                store = types.ModuleType("fr_b02b_protected_store")
                store.register = Mock(side_effect=AssertionError("no registration"))
                # B42-04 extends only the previously authorized case: it now
                # collects a human decision before the unchanged Store block.
                prompt = (Mock(side_effect=["ACCEPTED", ""]) if eligible else
                          Mock(side_effect=AssertionError("no prompt")))
                stdout, stderr = io.StringIO(), io.StringIO()
                with patch.object(windows_auth, "get_current_process_sid", return_value=SID), \
                        patch.object(allowlist, "managed_allowlist_source",
                                     return_value=source) as managed, \
                        patch.object(service, "prepare_review", side_effect=prepare_and_track), \
                        patch.dict(sys.modules, {"fr_b02b_protected_store": store}), \
                        patch.dict("os.environ", {"USERNAME": OTHER_SID}), \
                        patch.object(observation, "utc_now", return_value=when), \
                        patch("builtins.input", new=prompt), \
                        patch.object(uuid, "uuid4", wraps=uuid.uuid4) as new_id, \
                        redirect_stdout(stdout), redirect_stderr(stderr):
                    if mode == "unconfigured":
                        managed.side_effect = allowlist.AllowlistNotConfigured("not configured")
                    elif mode == "configuration-error":
                        managed.side_effect = PermissionError("private-managed-config")
                    code = run_cli(["review-register", "--zip", str(archive_path),
                                    "--record-dir", str(folder)], input_func=prompt)
                self.assertEqual(code, 1)
                if eligible:
                    self.assertIn("G5/G6 HOLD", stdout.getvalue())
                    self.assertNotIn("PROTECTED_REVIEW_RECORDED", stdout.getvalue())
                else:
                    self.assertEqual(stdout.getvalue(), "")
                self.assertEqual(stderr.getvalue(), "BLOCKED: " + category + "\n")
                self.assertEqual(next_stage, [SID] if eligible else [])
                if eligible:
                    self.assertEqual(prompt.call_count, 2)
                else:
                    prompt.assert_not_called()
                store.register.assert_not_called()
                new_id.assert_not_called()
                self.assertEqual({p: p.read_bytes() for p in original}, original)
                record = json.loads((folder / "observation.json").read_bytes())
                self.assertEqual((record["review_result"], record["publish_authorization"]),
                                 ("HOLD", "NONE"))


if __name__ == "__main__":
    unittest.main()
