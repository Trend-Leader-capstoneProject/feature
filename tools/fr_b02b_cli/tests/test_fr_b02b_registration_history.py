"""History through the internal service; real temporary I/O, synthetic ACL/Gate."""

from dataclasses import replace
from datetime import timedelta
import json
from unittest.mock import patch
import unittest
from uuid import UUID

import fr_b02b_registration as registration
import fr_b02b_review_service as service
import fr_b02b_protected_store as storage
import fr_b02b_observation as observation
import fr_b02b_restart as restart
import test_fr_b02b_registration_core as fixtures

RID2 = "REG-OBS-ffffffffffff4fffafffffffffffffff"


class RegistrationHistoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.RegistrationCoreTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.base = self.fixture.base

    def snapshot(self):
        return {p: p.read_bytes() for store in self.fixture.stores
                for p in store.root.rglob("*") if p.is_file()}

    def assert_blocked_without_changes(self):
        before = self.snapshot()
        with patch.object(registration, "uuid4", side_effect=AssertionError("blocked UUID forbidden")):
            with self.assertRaises(service.ReviewBlocked):
                self.fixture.call()
        self.assertEqual(self.snapshot(), before)

    def test_accepted_duplicate_revalidates_both_copies_without_uuid_or_writes(self):
        first = self.fixture.call()
        before = self.snapshot()
        # A fresh decision's fields must not replace the existing accepted event.
        self.base.pending = replace(self.base.pending, review_result="REJECTED",
                                    decision_reason="new explicit synthetic choice")
        with patch.object(registration, "uuid4", side_effect=AssertionError("duplicate UUID forbidden")), \
                patch.object(storage, "_write_exclusive", side_effect=AssertionError("duplicate write forbidden")):
            second = self.fixture.call()
        self.assertEqual(second.completion, first.completion)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(second.state, "HOLD")
        self.assertFalse(second.completion.external_eligible)

    def test_hold_and_rejected_require_new_explicit_event_and_preserve_parent(self):
        for initial in ("HOLD", "REJECTED"):
            with self.subTest(initial=initial):
                # Each case owns its own isolated store and Gate.
                case = fixtures.RegistrationCoreTests()
                case.setUp()
                try:
                    case.base.pending = replace(case.base.pending, review_result=initial,
                                                decision_reason="synthetic prior decision")
                    first = case.call()
                    old = {p: p.read_bytes() for folder in case.folders for p in folder.iterdir()}
                    case.base.pending = replace(
                        case.base.pending, review_result="ACCEPTED", decision_reason="",
                        reviewed_at_utc=case.now.isoformat().replace("+00:00", "Z"))
                    with patch.object(registration, "uuid4", return_value=UUID(RID2.removeprefix("REG-OBS-"))):
                        second = case.call()
                    self.assertNotEqual(first.completion.registration_id, second.completion.registration_id)
                    self.assertEqual(second.completion.registration_id, RID2)
                    for store in case.stores:
                        value = json.loads((store.root / "registrations" / RID2 / "registration.json").read_bytes())
                        self.assertEqual(value["supersedes_registration_id"], fixtures.RID)
                        self.assertEqual(value["review_result"], "ACCEPTED")
                        self.assertEqual(value["publish_authorization"], "NONE")
                    self.assertEqual({p: p.read_bytes() for p in old}, old)
                finally:
                    case.doCleanups()

    def test_partial_prior_registration_blocks_without_uuid_or_new_writes(self):
        self.fixture.call()
        (self.fixture.folders[1] / "registration_complete.json").unlink()
        self.assert_blocked_without_changes()

    def test_changed_valid_observation_with_same_id_blocks(self):
        self.fixture.call()
        folder = self.base.fixture.folder
        record = json.loads((folder / "observation.json").read_bytes())
        record["confirmed_at_utc"] = (observation._timestamp(record["confirmed_at_utc"])
                                      - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
        raw = observation.canonical_bytes(record)
        (folder / "observation.json").write_bytes(raw)  # Synthetic conflicting input.
        index = json.loads((folder / "index.json").read_bytes())
        index["artifact_sha256"] = observation.digest(raw)
        (folder / "index.json").write_bytes(observation.canonical_bytes(index))
        evidence = observation._load_verified_observation_snapshot(self.base.fixture.archive, folder)
        self.base.pending = replace(self.base.pending, evidence=evidence)
        self.assert_blocked_without_changes()

    def test_rehashed_but_unlinked_or_branched_history_is_not_reused(self):
        self.base.pending = replace(self.base.pending, review_result="HOLD", decision_reason="synthetic hold")
        self.fixture.call()
        # A second root is byte-valid and has matching C/E markers. Graph
        # validation must still reject it rather than choose the latest ID.
        for store, folder in zip(self.fixture.stores, self.fixture.folders):
            new = store.root / "registrations" / RID2
            new.mkdir()
            for name in registration.SOURCE_FILES:
                (new / name).write_bytes((folder / name).read_bytes())
            data = json.loads((folder / "registration.json").read_bytes())
            data["registration_id"] = RID2
            raw = observation.canonical_bytes(data)
            (new / "registration.json").write_bytes(raw)
            marker = registration.build_complete_marker(raw, self.base.pending.evidence, self.base.metadata())
            (new / "registration_complete.json").write_bytes(marker)
        self.assert_blocked_without_changes()

    def test_changed_backup_acl_prevents_accepted_reuse(self):
        self.fixture.call()
        self.fixture.stores[1].verify_protection.return_value = False
        self.assert_blocked_without_changes()

    def test_revocation_residue_is_not_ignored_or_reactivated(self):
        self.fixture.call()
        (self.fixture.folders[0] / "revocations").mkdir()
        self.assert_blocked_without_changes()

    def test_rereview_clock_rollback_is_blocked_before_uuid(self):
        self.base.pending = replace(self.base.pending, review_result="REJECTED", decision_reason="synthetic reject")
        self.fixture.call()
        self.base.pending = replace(self.base.pending, review_result="ACCEPTED", decision_reason="")
        self.assert_blocked_without_changes()  # Still using the OLD reviewed_at.

    def test_multiple_explicit_rereviews_form_one_chain_then_reuse_accepted_tip(self):
        self.base.pending = replace(self.base.pending, review_result="HOLD", decision_reason="synthetic hold")
        self.fixture.call()
        previous = fixtures.RID
        for rid, decision in ((RID2, "REJECTED"),
                              ("REG-OBS-2222222222224222a222222222222222", "HOLD"),
                              ("REG-OBS-3333333333334333a333333333333333", "ACCEPTED")):
            self.base.pending = replace(
                self.base.pending, review_result=decision, decision_reason="explicit synthetic rereview",
                reviewed_at_utc=self.fixture.now.isoformat().replace("+00:00", "Z"))
            with patch.object(registration, "uuid4", return_value=UUID(rid.removeprefix("REG-OBS-"))):
                receipt = self.fixture.call()
            self.assertEqual(receipt.completion.registration_id, rid)
            data = json.loads((self.fixture.stores[0].root / "registrations" / rid / "registration.json").read_bytes())
            self.assertEqual(data["supersedes_registration_id"], previous)
            previous = rid
        with patch.object(registration, "uuid4", side_effect=AssertionError("tip reuse UUID forbidden")):
            self.assertEqual(self.fixture.call().completion, receipt.completion)

    def test_rereview_partial_child_never_falls_back_to_parent_or_repairs_itself(self):
        self.base.pending = replace(self.base.pending, review_result="HOLD", decision_reason="synthetic hold")
        self.fixture.call()
        self.base.pending = replace(
            self.base.pending, review_result="ACCEPTED", decision_reason="",
            reviewed_at_utc=self.fixture.now.isoformat().replace("+00:00", "Z"))
        write = storage._write_exclusive
        def partial(path, raw):
            if path.parent.name == RID2 and path.name == "registration_complete.json" \
                    and path.is_relative_to(self.fixture.stores[1].root):
                write(path, raw[:4])
                raise OSError("synthetic partial child")
            write(path, raw)
        with patch.object(registration, "uuid4", return_value=UUID(RID2.removeprefix("REG-OBS-"))), \
                patch.object(storage, "_write_exclusive", side_effect=partial):
            with self.assertRaises(service.ReviewBlocked):
                self.fixture.call()
        self.assert_blocked_without_changes()

    def test_fresh_store_instances_reverify_and_read_only_restart_grants_no_permit(self):
        first = self.fixture.call()
        fresh = tuple(storage.ProtectedEvidenceStore(store.root, store.verify_protection)
                      for store in self.fixture.stores)
        before = self.snapshot()
        out = restart.inspect_registration_history(fresh, revalidate_environment=lambda: None)
        self.assertEqual(out.reason, "REGISTRATION_HISTORY_VERIFIED_RECHECK_REQUIRED")
        self.assertFalse(out.valid_registration)
        self.assertFalse(out.may_attempt_new_work)
        self.assertTrue(out.requires_gate_recheck)
        self.assertEqual(out.publish_authorization, "NONE")
        self.fixture.mirror.primary, self.fixture.mirror.backup = fresh
        with patch.object(registration, "uuid4", side_effect=AssertionError("fresh duplicate UUID forbidden")):
            second = self.fixture.call()
        self.assertEqual(first.completion, second.completion)
        self.assertEqual(self.snapshot(), before)
        (self.fixture.folders[1] / "index.json").write_bytes(b"corrupt synthetic index")
        self.assertEqual(restart.inspect_registration_history(
            fresh, revalidate_environment=lambda: None).reason, "REGISTRATION_HISTORY_UNVERIFIED")
        self.assert_blocked_without_changes()

    def test_duplicate_gate_release_failure_never_returns_receipt(self):
        from contextlib import contextmanager
        self.fixture.call()
        @contextmanager
        def release_failure():
            with self.fixture.fixture.fixture.exclusive_section():
                yield
            raise OSError("synthetic release failure")
        self.fixture.mirror.exclusive_section = release_failure
        self.assert_blocked_without_changes()


if __name__ == "__main__":
    unittest.main()
