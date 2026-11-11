"""Frozen revocation/current-state Core: isolated I/O, synthetic SID/ACL/Gate."""

from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
import json
from unittest.mock import patch
import unittest

import fr_b02b_observation as observation
import fr_b02b_protected_store as storage
import fr_b02b_registration as registration
import fr_b02b_restart as restart
import fr_b02b_review_service as service
import fr_b02b_windows_auth as auth
import test_fr_b02b_registration_core as fixtures


class RevocationTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.RegistrationCoreTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.mirror = self.case.mirror
        self.source = self.case.base.fixture.source
        self.sid = self.case.base.pending.reviewer_sid
        self.identity = patch.object(auth, "get_current_process_sid", return_value=self.sid)
        self.identity.start()
        self.addCleanup(self.identity.stop)

    def revoke(self, reason="synthetic withdrawal"):
        return self.mirror.revoke(fixtures.RID, reason=reason, allowlist_source=self.source)

    def verify(self):
        return self.mirror.verify_current(fixtures.RID, allowlist_source=self.source)

    def snapshot(self):
        return {p: p.read_bytes() for store in self.case.stores
                for p in store.root.rglob("*") if p.is_file()}

    def test_append_only_frozen_event_and_verified_duplicate_and_restart(self):
        self.case.call()
        before = self.snapshot()
        writer = storage._write_exclusive

        def guarded(path, raw):
            self.assertTrue(self.case.fixture.fixture.locked)
            self.assertEqual(path.parent.name, "revocations")
            writer(path, raw)

        with patch.object(storage, "_write_exclusive", side_effect=guarded) as writes:
            result = self.revoke()
        self.assertEqual(writes.call_count, 2)
        self.assertEqual(result.status, "REVOKED_LOCAL_REGISTRATION")
        self.assertEqual(result.publish_authorization, "NONE")
        self.assertFalse(result.external_eligible)
        for path, raw in before.items():
            self.assertEqual(path.read_bytes(), raw)
        events = [(folder / "revocations" / (result.event_id + ".json")).read_bytes()
                  for folder in self.case.folders]
        self.assertEqual(events[0], events[1])
        value = json.loads(events[0])
        self.assertEqual(set(value), registration.REVOKE_KEYS)
        self.assertEqual(value["schema"], "FR_B02B_REVOKE_V1")
        self.assertEqual(value["revoker_sid"], self.sid)
        self.assertEqual(events[0], observation.canonical_bytes(value))
        self.assertEqual(value["registration_sha256"], observation.digest(
            (self.case.folders[0] / "registration.json").read_bytes()))
        after = self.snapshot()
        with patch.object(registration, "uuid4", side_effect=AssertionError("no duplicate UUID")), \
                patch.object(storage, "_write_exclusive", side_effect=AssertionError("no duplicate write")):
            self.assertEqual(self.revoke("another reason"), result)
            state = self.verify()
            self.assertEqual(state.status, "PASS_PROTECTED_LOCAL_INTEGRITY_ONLY")
            self.assertEqual(state.effective_review_state, "REVOKED")
            with self.assertRaises(service.ReviewBlocked):
                self.case.call()
        self.assertEqual(self.snapshot(), after)
        fresh = tuple(storage.ProtectedEvidenceStore(s.root, s.verify_protection) for s in self.case.stores)
        assessment = restart.inspect_registration_history(fresh, revalidate_environment=lambda: None,
                                                         registration_id=fixtures.RID)
        self.assertEqual(assessment.effective_review_state, "REVOKED")
        self.assertFalse(assessment.valid_registration)
        self.assertTrue(assessment.requires_gate_recheck)

    def test_hold_integrity_pass_cannot_revoke(self):
        self.case.base.pending = replace(self.case.base.pending, review_result="HOLD",
                                         decision_reason="synthetic hold")
        self.case.call()
        self.assertEqual(self.verify().effective_review_state, "HOLD")
        before = self.snapshot()
        with self.assertRaises(storage.StagingError):
            self.revoke()
        self.assertEqual(self.snapshot(), before)

    def test_rejected_integrity_pass_cannot_revoke(self):
        self.case.base.pending = replace(self.case.base.pending, review_result="REJECTED",
                                         decision_reason="synthetic rejection")
        self.case.call()
        self.assertEqual(self.verify().effective_review_state, "REJECTED")
        with self.assertRaises(storage.StagingError):
            self.revoke()

    def test_accepted_integrity_pass_and_invalid_reasons_never_write(self):
        self.case.call()
        self.assertEqual(self.verify().effective_review_state, "ACCEPTED")
        before = self.snapshot()
        for reason in (None, "", "  ", 1):
            with self.subTest(reason=reason), self.assertRaises(storage.StagingError):
                self.revoke(reason)
        self.assertEqual(self.snapshot(), before)

    def test_partial_backup_event_blocks_verify_retry_register_and_restart(self):
        self.case.call()
        writer = storage._write_exclusive

        def partial(path, raw):
            if path.parent.name == "revocations" and path.is_relative_to(self.case.stores[1].root):
                writer(path, raw[:4])
                raise OSError("synthetic partial event")
            writer(path, raw)

        with patch.object(storage, "_write_exclusive", side_effect=partial), \
                self.assertRaises(storage.StagingError):
            self.revoke()
        self.assert_corrupt_history_blocked()

    def assert_corrupt_history_blocked(self):
        before = self.snapshot()
        for call in (self.verify, self.revoke):
            with self.assertRaises(storage.StagingError):
                call()
        with self.assertRaises(service.ReviewBlocked):
            self.case.call()
        assessment = restart.inspect_registration_history(self.case.stores,
            revalidate_environment=lambda: None, registration_id=fixtures.RID)
        self.assertEqual(assessment.reason, "REGISTRATION_HISTORY_UNVERIFIED")
        self.assertIsNone(assessment.effective_review_state)
        self.assertEqual(self.snapshot(), before)

    def test_one_sided_missing_event_blocks(self):
        self.case.call()
        event = self.revoke()
        (self.case.folders[1] / "revocations" / (event.event_id + ".json")).unlink()
        self.assert_corrupt_history_blocked()

    def test_individually_valid_but_different_ce_events_block(self):
        self.case.call()
        event = self.revoke()
        path = self.case.folders[1] / "revocations" / (event.event_id + ".json")
        value = json.loads(path.read_bytes())
        value["reason"] = "different synthetic reason"
        path.write_bytes(observation.canonical_bytes(value))
        self.assert_corrupt_history_blocked()

    def test_sid_loss_after_primary_write_leaves_hold_and_retry_never_repairs(self):
        self.case.call()
        writer = storage._write_exclusive

        def lose_authority(path, raw):
            writer(path, raw)
            if path.parent.name == "revocations":
                self.identity_mock.return_value = "S-1-5-21-999"

        with patch.object(auth, "get_current_process_sid", return_value=self.sid) as self.identity_mock, \
                patch.object(storage, "_write_exclusive", side_effect=lose_authority), \
                self.assertRaises(storage.StagingError):
            self.revoke()
        self.assert_corrupt_history_blocked()

    def test_unexpected_revocation_file_and_empty_directories_are_hold(self):
        self.case.call()
        for folder in self.case.folders:
            (folder / "revocations").mkdir()
        self.assert_corrupt_history_blocked()
        for folder in self.case.folders:
            (folder / "revocations" / "unexpected.txt").write_bytes(b"unexpected")
        self.assert_corrupt_history_blocked()

    def test_matching_but_tampered_event_schema_links_and_clock_block(self):
        self.case.call()
        event = self.revoke()
        paths = [folder / "revocations" / (event.event_id + ".json") for folder in self.case.folders]
        original = paths[0].read_bytes()
        value = json.loads(original)
        invalid = [original + b"\n", b"{", original.replace(b'{', b'{"reason":"duplicate",', 1)]
        for key, replacement in (("registration_sha256", "sha256:" + "0" * 64),
                                 ("registration_id", "REG-OBS-" + "0" * 32),
                                 ("event_id", "REV-OBS-" + "0" * 32), ("schema", "OTHER"),
                                 ("revoker_sid", "invalid"), ("reason", " "),
                                 ("publish_authorization", "YES"),
                                 ("revoked_at_utc", "2099-01-01T00:00:00Z"),
                                 ("revoked_at_utc", "2000-01-01T00:00:00Z"),
                                 ("revoked_at_utc", "2026-01-01T00:00:00")):
            invalid.append(observation.canonical_bytes(dict(value, **{key: replacement})))
        invalid.append(observation.canonical_bytes(dict(value, extra="unexpected")))
        for raw in invalid:
            with self.subTest(raw=raw[:24]):
                for path in paths:
                    path.write_bytes(raw)
                for call in (self.verify, self.revoke):
                    with self.assertRaises(storage.StagingError):
                        call()
        for path in paths:
            path.write_bytes(original)
        self.assertEqual(self.verify().effective_review_state, "REVOKED")

    def test_authority_layout_and_original_corruption_block_before_writes(self):
        self.case.call()
        before = self.snapshot()
        with patch.object(auth, "get_current_process_sid", return_value="S-1-5-21-999"), \
                self.assertRaises(storage.StagingError):
            self.revoke()
        self.assertEqual(self.snapshot(), before)
        self.case.stores[1].verify_protection.return_value = False
        with self.assertRaises(storage.StagingError):
            self.revoke()
        self.case.stores[1].verify_protection.return_value = True
        self.mirror.verify_layout.return_value = False
        with self.assertRaises(storage.StagingError):
            self.revoke()
        self.mirror.verify_layout.return_value = True
        (self.case.folders[1] / "observation.json").write_bytes(b"corrupt")
        self.assert_corrupt_history_blocked()

    def test_clock_rollback_blocks_before_event_write(self):
        self.case.call()
        before = self.snapshot()
        with patch.object(observation, "utc_now", return_value=self.case.now - timedelta(seconds=1)), \
                self.assertRaises(storage.StagingError):
            self.revoke()
        self.assertEqual(self.snapshot(), before)

    def test_gate_release_failure_never_returns_revocation_receipt(self):
        self.case.call()
        gate = self.mirror.exclusive_section

        @contextmanager
        def failed_release():
            with gate():
                yield
            raise OSError("synthetic gate release failure")

        self.mirror.exclusive_section = failed_release
        with self.assertRaises(storage.StagingError):
            self.revoke()
        self.mirror.exclusive_section = gate
        self.assertEqual(self.verify().effective_review_state, "REVOKED")


if __name__ == "__main__":
    unittest.main()
