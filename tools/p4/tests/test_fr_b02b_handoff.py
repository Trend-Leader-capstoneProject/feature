"""Composition with existing synthetic protected-store fixtures, never Native proof."""

import unittest
from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import patch
from uuid import UUID

import fr_b02b_handoff as handoff
import fr_b02b_registration as registration
import fr_b02b_windows_auth as auth
import test_fr_b02b_registration_core as fixtures
from fr_b02b_binding import ExpectedBinding
from fr_b02b_observation import digest

RID = fixtures.RID


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.RegistrationCoreTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.source = self.case.base.fixture.source
        self.identity = patch.object(handoff, "require_process_sid",
                                     return_value=self.case.base.pending.reviewer_sid)
        self.identity.start()
        self.addCleanup(self.identity.stop)

    def prepare(self, decision="ACCEPTED"):
        self.case.base.pending = replace(self.case.base.pending, review_result=decision,
                                        decision_reason="synthetic review")
        self.case.call()
        evidence = self.case.base.pending.evidence
        manifest = (self.case.folders[0] / "registration.json").read_bytes()
        self.expected = ExpectedBinding(
            **{key: evidence.record[key] for key in
               ("trend_ref", "content_ref", "review_evidence_id", "source_url")},
            local_evidence_id=evidence.record["evidence_id"], registration_id=RID,
            registration_sha256=digest(manifest),
            a1_archive_sha256=digest(evidence.a1_snapshot.archive_bytes),
            observation_sha256=digest(evidence.record_bytes), index_sha256=digest(evidence.index_bytes))

    def inspect(self):
        result = handoff.inspect_handoff(self.case.mirror, self.expected, allowlist_source=self.source)
        self.assertEqual((result.operational_handoff, result.publish_authorization,
                          result.observation_time), ("HOLD", "NONE", "HOLD"))
        return result

    def test_latest_decisions_are_diagnostic_and_read_only(self):
        self.prepare()
        before = {p: p.read_bytes() for folder in self.case.folders for p in folder.iterdir()}
        result = self.inspect()
        self.assertEqual((result.binding_status, result.latest_registration,
                          result.current_review_state), ("MATCH", True, "ACCEPTED"))
        self.assertEqual(result.protected_inventory, "UNVERIFIED")
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_hold(self):
        self.prepare("HOLD")
        self.assertEqual(self.inspect().current_review_state, "HOLD")

    def test_rejected(self):
        self.prepare("REJECTED")
        self.assertEqual(self.inspect().current_review_state, "REJECTED")

    def test_fingerprint_mismatch(self):
        self.prepare()
        self.expected = replace(self.expected, registration_sha256="sha256:" + "0" * 64)
        self.assertEqual(self.inspect().reason, "BINDING_FAILED")

    def test_revoked(self):
        self.prepare()
        with patch.object(auth, "get_current_process_sid", return_value=self.case.base.pending.reviewer_sid):
            self.case.mirror.revoke(RID, reason="synthetic revocation", allowlist_source=self.source)
        self.assertEqual(self.inspect().current_review_state, "REVOKED")

    def test_superseded_registration(self):
        self.prepare("HOLD")
        self.case.base.pending = replace(
            self.case.base.pending, review_result="ACCEPTED",
            reviewed_at_utc=self.case.now.isoformat().replace("+00:00", "Z"))
        with patch.object(registration, "uuid4", return_value=UUID("ffffffffffff4fffafffffffffffffff")):
            self.case.call()
        result = self.inspect()
        self.assertEqual(result.binding_status, "MATCH")
        self.assertFalse(result.latest_registration)
        self.assertEqual(result.reason, "REGISTRATION_NOT_LATEST")

    def test_missing_marker(self):
        self.prepare()
        (self.case.folders[1] / "registration_complete.json").unlink()
        self.assertEqual(self.inspect().binding_status, "UNVERIFIED")

    def test_authentication_failure(self):
        self.prepare()
        with patch.object(handoff, "require_process_sid", side_effect=ValueError("unavailable")):
            self.assertEqual(self.inspect().reason, "PROTECTED_HISTORY_UNVERIFIED")

    def test_inventory_unavailable(self):
        self.prepare()
        with patch.object(registration, "_final_inventory", side_effect=ValueError("unavailable")):
            self.assertEqual(self.inspect().binding_status, "UNVERIFIED")

    def test_untrusted_state_objects_are_not_evidence(self):
        self.prepare()
        for value in (True, "ACCEPTED", registration.CurrentReviewState(RID, "ACCEPTED")):
            result = handoff.inspect_handoff(value, self.expected, allowlist_source=self.source)
            self.assertEqual(result.binding_status, "UNVERIFIED")
            self.assertEqual(result.publish_authorization, "NONE")

    def test_gate_release_failure_suppresses_result(self):
        self.prepare()
        original = self.case.mirror.exclusive_section

        @contextmanager
        def failure():
            with original():
                yield
                raise OSError("release failed")

        self.case.mirror.exclusive_section = failure
        self.assertEqual(self.inspect().binding_status, "UNVERIFIED")

    def test_mutation_during_binding_is_detected_before_release(self):
        self.prepare()
        original = handoff.verify_binding

        def changed(**kwargs):
            self.assertTrue(self.case.fixture.fixture.locked)
            result = original(**kwargs)
            path = self.case.folders[1] / "registration.json"
            path.write_bytes(path.read_bytes() + b" ")
            return result

        with patch.object(handoff, "verify_binding", side_effect=changed):
            self.assertEqual(self.inspect().binding_status, "UNVERIFIED")
