"""B42-04: real synthetic validators; fake SID/protection/clock, no Store."""

import io
import json
import sys
import tempfile
import types
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
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

SID = "S-1-5-21-100-200-300-1001"  # Synthetic only.


class ReviewDecisionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.archive = self.root / "synthetic.zip"
        approvals, batch = example()
        with ZipFile(self.archive, "w") as archive:
            archive.writestr(a1.A1_ZIP_APPROVALS, json.dumps(approvals))
            archive.writestr(a1.A1_ZIP_BATCH, json.dumps(batch))
        self.snapshot = a1.load_a1_snapshot(self.archive)
        self.observed_at = datetime(2026, 11, 10, 8, tzinfo=timezone.utc)
        self.reviewed_at = self.observed_at + timedelta(seconds=10)
        with patch.object(observation, "utc_now", return_value=self.observed_at):
            saved = observation.record_observation(
                self.snapshot, self.archive, self.root / "observations", self.observed_at
            )
        self.folder = Path(saved["directory"])
        self.record = json.loads((self.folder / "observation.json").read_bytes())
        path = self.root / "synthetic-reviewers.json"
        path.write_text(json.dumps({"schema": allowlist.SCHEMA, "reviewers": [
            {"sid": SID, "active": True, "role": "EVIDENCE_REVIEWER"},
        ]}), encoding="utf-8")
        self.source = allowlist.AllowlistSource(path, Mock(return_value=True))

    def files(self):
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}

    def collect(self, request):
        with patch.object(windows_auth, "get_current_process_sid", return_value=SID):
            return service.collect_review_decision(
                self.archive, self.folder, request_decision=request,
                allowlist_source=self.source,
            )

    def invoke(self, answers, *, sid=SID):
        prompt = Mock(side_effect=answers)
        store = types.ModuleType("fr_b02b_protected_store")
        store.register = Mock(side_effect=AssertionError("no Store registration"))
        stdout, stderr = io.StringIO(), io.StringIO()
        before = self.files()
        with patch.object(windows_auth, "get_current_process_sid", return_value=sid), \
                patch.object(allowlist, "managed_allowlist_source", return_value=self.source), \
                patch.object(observation, "utc_now", return_value=self.reviewed_at), \
                patch.dict(sys.modules, {"fr_b02b_protected_store": store}), \
                patch.object(uuid, "uuid4", wraps=uuid.uuid4) as ids, \
                patch("builtins.input", new=prompt), \
                patch("webbrowser.open", side_effect=AssertionError("no browser")), \
                patch("socket.create_connection", side_effect=AssertionError("no HTTP")), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            code = run_cli(["review-register", "--zip", str(self.archive),
                            "--record-dir", str(self.folder)], input_func=prompt)
        store.register.assert_not_called()
        ids.assert_not_called()
        self.assertEqual(self.files(), before)
        combined = stdout.getvalue() + stderr.getvalue()
        for forbidden in ("PROTECTED_REVIEW_RECORDED", "REG-OBS-", "registration_id", SID):
            self.assertNotIn(forbidden, combined)
        return code, stdout.getvalue(), stderr.getvalue(), prompt

    def test_explicit_choices_return_only_pending_decisions_with_original_bytes(self):
        for state, reason in (("ACCEPTED", ""), ("ACCEPTED", "검토 근거"),
                              ("HOLD", "추가 확인 필요"), ("REJECTED", "근거 불일치"),
                              ("HOLD", "가" * 500)):
            with self.subTest(state=state, length=len(reason)):
                request = Mock(return_value=(state, reason))
                before = self.files()
                with patch.object(observation, "utc_now", return_value=self.reviewed_at):
                    result = self.collect(request)
                self.assertIsNotNone(result, "a pending human decision must be returned")
                self.assertEqual(result.review_result, state)
                self.assertEqual(result.decision_reason, reason)
                self.assertEqual(result.reviewer_sid, SID)
                self.assertEqual(result.local_evidence_id, self.folder.name)
                self.assertEqual(result.publish_authorization, "NONE")
                self.assertFalse(hasattr(result, "registration_id"))
                self.assertEqual(result.evidence.a1_snapshot.archive_bytes,
                                 self.archive.read_bytes())
                self.assertEqual(result.evidence.record_bytes,
                                 (self.folder / "observation.json").read_bytes())
                self.assertEqual(result.evidence.index_bytes,
                                 (self.folder / "index.json").read_bytes())
                self.assertEqual(self.files(), before)

    def test_empty_selection_cancels_and_unknown_selection_never_accepts(self):
        for choice in ("", "  ", "YES", "APPROVED", "unknown"):
            with self.subTest(choice=choice):
                expected = service.ReviewCancelled if not choice.strip() else service.ReviewBlocked
                with patch.object(observation, "utc_now", return_value=self.reviewed_at):
                    with self.assertRaises(expected):
                        self.collect(Mock(return_value=(choice, "")))

    def test_hold_rejected_require_reason_and_all_reasons_are_bounded(self):
        for state, reason in (("HOLD", ""), ("REJECTED", " \t"),
                              ("ACCEPTED", "가" * 501), ("HOLD", "가" * 501),
                              ("REJECTED", "가" * 501)):
            with self.subTest(state=state, length=len(reason)):
                with patch.object(observation, "utc_now", return_value=self.reviewed_at):
                    with self.assertRaises(service.ReviewBlocked):
                        self.collect(Mock(return_value=(state, reason)))

    def test_preview_and_timestamp_use_verified_values_and_clock_after_decision(self):
        events = []

        def clock():
            events.append("clock")
            return self.reviewed_at

        def decide(preview):
            events.append("decision")
            self.assertEqual(preview.title, self.snapshot.title)
            self.assertEqual(preview.summary, self.snapshot.summary)
            self.assertEqual(preview.source_url, self.snapshot.source_url)
            self.assertEqual(preview.confirmed_at_utc, self.record["confirmed_at_utc"])
            self.assertEqual(preview.record_created_at_utc, self.record["record_created_at_utc"])
            self.assertEqual(preview.observer_ref, "UNVERIFIED_LOCAL_OPERATOR")
            self.assertEqual(preview.actor_assurance, "UNVERIFIED")
            return "ACCEPTED", ""

        with patch.object(observation, "utc_now", side_effect=clock):
            result = self.collect(decide)
        self.assertIsNotNone(result)
        self.assertEqual(events, ["clock", "decision", "clock"])
        self.assertEqual(result.reviewed_at_utc, "2026-11-10T08:00:10Z")

    def test_invalid_or_backwards_clock_blocks(self):
        for times in ((None,), (datetime(2026, 11, 10, 8),),
                      (self.observed_at - timedelta(seconds=1),),
                      (self.reviewed_at, self.observed_at),
                      (self.reviewed_at, OSError("private-clock-error"))):
            with self.subTest(times=times):
                request = Mock(return_value=("ACCEPTED", ""))
                with patch.object(observation, "utc_now", side_effect=times):
                    with self.assertRaisesRegex(service.ReviewBlocked, "clock"):
                        self.collect(request)

    def test_auth_failure_prevents_review_callback(self):
        request = Mock(side_effect=AssertionError("no review without authorization"))
        with patch.object(windows_auth, "get_current_process_sid", side_effect=OSError("private")):
            with self.assertRaises(service.ReviewBlocked):
                service.collect_review_decision(self.archive, self.folder,
                                                request_decision=request,
                                                allowlist_source=self.source)
        request.assert_not_called()

    def test_cli_displays_preview_but_all_decisions_still_block_registration(self):
        for state, reason in (("ACCEPTED", ""), ("HOLD", "추가 확인"),
                              ("REJECTED", "불일치")):
            with self.subTest(state=state):
                code, stdout, stderr, prompt = self.invoke([state, reason])
                self.assertEqual(code, 1)
                self.assertEqual(stderr, "BLOCKED: protected review registration is not configured\n")
                self.assertEqual(prompt.call_count, 2)
                for value in (self.snapshot.title, self.snapshot.summary, self.snapshot.source_url,
                              self.record["confirmed_at_utc"], self.record["record_created_at_utc"],
                              "UNVERIFIED_LOCAL_OPERATOR", "UNVERIFIED", "NONE", "G5/G6 HOLD"):
                    self.assertIn(value, stdout)

    def test_cli_cancel_input_errors_and_no_extra_yes_confirmation(self):
        for answers, code, message, count in (
            ([""], 2, "CANCELLED", 1), ([EOFError()], 2, "CANCELLED", 1),
            ([KeyboardInterrupt()], 2, "CANCELLED", 1),
            (["YES"], 1, "invalid review decision", 1),
            (["HOLD", " "], 1, "review reason required", 2),
            (["ACCEPTED", "가" * 501], 1, "invalid review reason", 2),
            (["ACCEPTED", EOFError()], 2, "CANCELLED", 2),
            ([OSError("private-input-error")], 1, "review input unavailable", 1),
        ):
            with self.subTest(message=message, answers=repr(answers)[:40]):
                actual, stdout, stderr, prompt = self.invoke(answers)
                self.assertEqual(actual, code)
                self.assertIn(message, stdout + stderr)
                self.assertEqual(prompt.call_count, count)
                self.assertNotIn("private-input-error", stdout + stderr)

    def test_cli_unauthorized_has_no_preview_or_prompt(self):
        code, stdout, stderr, prompt = self.invoke(
            [AssertionError("no prompt")], sid="S-1-5-21-100-200-300-1002"
        )
        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "BLOCKED: reviewer is not authorized\n")
        prompt.assert_not_called()

    def test_cli_programming_error_is_distinct_and_sanitized_and_interrupt_cancels(self):
        for failure, expected, category in (
            (TypeError("private-programming-diagnostic"), 1,
             "BLOCKED: internal review failure (TypeError)"),
            (KeyboardInterrupt(), 2, "CANCELLED"),
        ):
            with self.subTest(failure=type(failure).__name__):
                self.source = allowlist.AllowlistSource(
                    self.source.path, Mock(side_effect=failure)
                )
                try:
                    code, stdout, stderr, prompt = self.invoke([])
                except KeyboardInterrupt:
                    self.fail("CLI must return cancellation code 2 instead of propagating interrupt")
                self.assertEqual(code, expected)
                self.assertIn(category, stdout + stderr)
                self.assertNotIn("private-programming-diagnostic", stdout + stderr)
                self.assertNotIn(str(self.root), stdout + stderr)
                prompt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
