"""Isolated helper boundary: synthetic identities/bytes, no IPC or Native I/O."""

from contextlib import contextmanager
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

import fr_b02b_helper_core as helper
import fr_b02b_observation as observation
from fr_b02b_review_service import ReviewBlocked, ReviewCancelled
import test_fr_b02b_protected_store as fixtures

SID = "S-1-5-21-100-200-300-1001"
OTHER = "S-1-5-21-100-200-300-1002"
RID = "REG-OBS-1234567812344234a234123456789abc"


class Peer(helper.AuthenticatedPeer):
    sid = SID
    failure = None

    def requester_sid(self):
        return self.sid

    def revalidate(self):
        if self.failure:
            raise self.failure


class Authenticator(helper.RequestAuthenticator):
    def __init__(self, peer):
        self.peer = peer

    @contextmanager
    def authenticate(self):
        yield self.peer


class Creation(helper.ProtectedCreationBoundary, helper.CreationSession):
    """Contract double only; never claims protected filesystem verification."""

    def __init__(self):
        self.locked = False
        self.calls = 0
        self.ledger = {}
        self.fault = None
        self.change = lambda: None
        self.valid = True

    @contextmanager
    def exclusive_section(self):
        if self.locked:
            raise OSError("nested Gate")
        self.locked = True
        try:
            yield self
            if self.fault == "release":
                raise OSError("private release diagnostics")
        finally:
            self.locked = False

    def apply(self, request, evidence, checkpoint):
        assert self.locked
        checkpoint()
        self.calls += 1
        self.change()
        checkpoint()
        key = (evidence.record["evidence_id"] if evidence else request.registration_id)
        if key in self.ledger and self.ledger[key] != request:
            raise ValueError("conflicting evidence or revocation binding")
        self.ledger[key] = request
        if self.fault == "partial":
            raise OSError("private partial-write diagnostics")
        return key

    def verify(self, request, result, checkpoint):
        assert self.locked
        checkpoint()
        return self.valid and self.ledger.get(result) == request


class HelperCoreTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.ProtectedStoreTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        evidence = self.case.pending.evidence
        self.request = helper.RegisterRequest(self.case.metadata(),
            evidence.a1_snapshot.archive_bytes, evidence.record_bytes, evidence.index_bytes)
        self.peer = Peer()
        self.creation = Creation()
        self.clock = patch.object(observation, "utc_now", return_value=self.case.fixture.reviewed_at)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def core(self, peer=None):
        return helper.HelperRequestCore(authenticator=Authenticator(self.peer if peer is None else peer),
            creation=self.creation, allowlist_source=self.case.fixture.source)

    def test_body_sid_is_not_authenticated_sid(self):
        # Both are authorized: authorization alone must not hide the mismatch.
        source = self.case.fixture.source
        value = json.loads(source.path.read_bytes())
        value["reviewers"].append(dict(sid=OTHER, active=True, role="EVIDENCE_REVIEWER"))
        source.path.write_bytes(observation.canonical_bytes(value))
        self.peer.sid = OTHER
        with self.assertRaises(ReviewBlocked):
            self.core().execute(self.request)
        self.assertEqual(self.creation.calls, 0)

    def test_no_default_or_string_authentication_path(self):
        for core in (helper.HelperRequestCore(), self.core(SID)):
            with self.assertRaises(ReviewBlocked):
                core.execute(self.request)
        self.assertEqual(self.creation.calls, 0)

    def test_register_reuses_validators_and_never_uses_helper_process_sid(self):
        before = self.case.originals()
        with patch("fr_b02b_windows_auth.get_current_process_sid",
                   side_effect=AssertionError("helper token is not reviewer")):
            receipt = self.core().execute(self.request)
        self.assertEqual(receipt.publish_authorization, "NONE")
        self.assertFalse(receipt.external_eligible)
        self.assertEqual(self.case.originals(), before)
        self.assertFalse(self.creation.locked)

    def test_strict_request_types_and_changed_bytes_block_before_creation(self):
        pending = json.loads(self.request.pending_bytes)
        bad = [None, {}, "register", replace(self.request, archive_bytes=b"bad"),
               replace(self.request, observation_bytes=self.request.observation_bytes + b"changed"),
               replace(self.request, index_bytes=b"{}"),
               replace(self.request, pending_bytes=observation.canonical_bytes(dict(pending, path="C:/"))),
               replace(self.request, pending_bytes=observation.canonical_bytes(dict(pending, review_result=""))),
               replace(self.request, pending_bytes=observation.canonical_bytes(dict(pending,
                   a1_archive_sha256="sha256:" + "0" * 64))),
               replace(self.request, archive_bytes=bytearray(self.request.archive_bytes))]
        for request in bad:
            with self.subTest(request_type=type(request)), self.assertRaises(ReviewBlocked):
                self.core().execute(request)
        self.assertEqual(self.creation.calls, 0)

    def test_allowlist_and_live_identity_rechecked_inside_gate(self):
        for change in (lambda: setattr(self.peer, "sid", OTHER),
                       lambda: setattr(self.peer, "failure", OSError("private token error")),
                       lambda: self.case.fixture.source.path.write_bytes(b"damaged")):
            self.creation.change = change
            with self.assertRaises(ReviewBlocked) as error:
                self.core().execute(self.request)
            self.assertNotIn("private", str(error.exception))
            self.assertEqual(self.creation.ledger, {})
            self.peer.sid, self.peer.failure = SID, None

    def test_untrusted_or_inactive_allowlist_never_calls_creation(self):
        source = self.case.fixture.source
        raw = source.path.read_bytes()
        for value in (b"damaged", raw.replace(b'true', b'false')):
            source.path.write_bytes(value)
            with self.assertRaises(ReviewBlocked):
                self.core().execute(self.request)
        source.path.write_bytes(raw)
        source.verify_protection.return_value = False
        with self.assertRaises(ReviewBlocked):
            self.core().execute(self.request)
        self.assertEqual(self.creation.calls, 0)

    def test_cancel_partial_failure_verification_and_release_fail_closed(self):
        self.peer.failure = ReviewCancelled()
        with self.assertRaises(ReviewCancelled):
            self.core().execute(self.request)
        self.assertEqual(self.creation.calls, 0)
        self.peer.failure = None
        for fault in ("partial", "release", "verify"):
            self.creation.fault = fault
            self.creation.valid = fault != "verify"
            core = self.core()
            with self.assertRaises(ReviewBlocked):
                core.execute(self.request)
            self.assertTrue(self.creation.ledger)  # Never automatically cleaned up.
            with self.assertRaises(ReviewBlocked):
                core.execute(self.request)
        self.assertFalse(self.creation.locked)

    def test_one_shot_attempt_and_history_duplicate_contract(self):
        core = self.core()
        core.execute(self.request)
        with self.assertRaises(ReviewBlocked):
            core.execute(self.request)
        self.core().execute(self.request)  # Fresh session must reverify history.
        self.assertEqual(len(self.creation.ledger), 1)
        pending = json.loads(self.request.pending_bytes)
        changed = replace(self.request, pending_bytes=observation.canonical_bytes(
            dict(pending, review_result="REJECTED", decision_reason="changed judgment")))
        with self.assertRaises(ReviewBlocked):
            self.core().execute(changed)
        self.assertEqual(len(self.creation.ledger), 1)

    def test_reentrant_attempt_cannot_enter_second_gate(self):
        core = self.core()

        def reenter():
            with self.assertRaises(ReviewBlocked):
                core.execute(self.request)

        self.creation.change = reenter
        core.execute(self.request)
        self.assertEqual(self.creation.calls, 1)

    def test_hold_rejected_and_duplicate_pending_keys(self):
        pending = json.loads(self.request.pending_bytes)
        for state in ("HOLD", "REJECTED"):
            request = replace(self.request, pending_bytes=observation.canonical_bytes(
                dict(pending, review_result=state, decision_reason="human reason")))
            self.creation.ledger.clear()
            self.core().execute(request)
            self.assertEqual(next(iter(self.creation.ledger.values())), request)
        duplicate = self.request.pending_bytes[:-1] + b',"reviewer_sid":"' + SID.encode() + b'"}'
        with self.assertRaises(ReviewBlocked):
            self.core().execute(replace(self.request, pending_bytes=duplicate))

    def test_late_cancellation_retains_residue_without_receipt(self):
        def cancelled(request, result, checkpoint):
            self.peer.failure = ReviewCancelled()
            checkpoint()

        self.creation.verify = cancelled
        with self.assertRaises(ReviewCancelled):
            self.core().execute(self.request)
        self.assertTrue(self.creation.ledger)
        self.assertFalse(self.creation.locked)

    def test_suppressed_scope_failures_cannot_return_receipt(self):
        class SuppressingAuth(Authenticator):
            @contextmanager
            def authenticate(self):
                try:
                    yield self.peer
                except ValueError:
                    pass

        self.peer.failure = ValueError("private identity error")
        core = helper.HelperRequestCore(authenticator=SuppressingAuth(self.peer),
            creation=self.creation, allowlist_source=self.case.fixture.source)
        with self.assertRaises(ReviewBlocked):
            core.execute(self.request)

        class SuppressingCreation(Creation):
            @contextmanager
            def exclusive_section(self):
                try:
                    with super().exclusive_section() as session:
                        yield session
                except OSError:
                    pass

        self.peer.failure = None
        self.creation = SuppressingCreation()
        self.creation.fault = "partial"
        with self.assertRaises(ReviewBlocked):
            self.core().execute(self.request)

    def test_authentication_scope_release_failure_suppresses_receipt(self):
        class FailingAuth(Authenticator):
            @contextmanager
            def authenticate(self):
                yield self.peer
                raise OSError("private authentication release failure")

        core = helper.HelperRequestCore(authenticator=FailingAuth(self.peer),
            creation=self.creation, allowlist_source=self.case.fixture.source)
        with self.assertRaises(ReviewBlocked):
            core.execute(self.request)
        self.assertTrue(self.creation.ledger)

    def test_revoke_contract_requires_target_hash_reason_and_authenticated_sid(self):
        request = helper.RevokeRequest(RID, "sha256:" + "1" * 64, SID, "withdrawal")
        self.core().execute(request)
        self.core().execute(request)
        for bad in (replace(request, registration_id="../other"),
                    replace(request, registration_sha256="invalid"),
                    replace(request, reason=" "), replace(request, reason="x" * 501),
                    replace(request, revoker_sid=OTHER),
                    replace(request, registration_sha256="sha256:" + "2" * 64)):
            with self.subTest(bad=type(bad)), self.assertRaises(ReviewBlocked):
                self.core().execute(bad)
        self.assertEqual(len(self.creation.ledger), 1)
