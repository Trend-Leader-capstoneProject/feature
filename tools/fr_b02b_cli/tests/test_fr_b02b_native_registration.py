"""Isolated final-object authority double; no operating Native capability."""

from dataclasses import replace
from datetime import timedelta
import json
from unittest.mock import Mock, patch
import unittest

import fr_b02b_inventory as inventory
import fr_b02b_native_store as native
import fr_b02b_observation as observation
import fr_b02b_registration as registration
import fr_b02b_protected_store as storage
import fr_b02b_windows_store as windows
import fr_b02b_review_service as service
import fr_b02b_windows_auth as auth
import test_fr_b02b_inventory as fixtures


class NativeRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.InventoryTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.api = self.fixture.fixture.api
        self.base = self.fixture.fixture.base
        policy = self.fixture.policy
        specs = []
        for root in (policy.primary, policy.backup):
            path = root / "registrations"
            path.mkdir()
            info = native.ObjectInfo(path, (1, f"{len(self.api.records) + 100:032x}"),
                                     self.fixture.protection.root.acl, True, False, 1)
            self.api.records[path] = info
            specs.append(native.ApprovedObject(path, info.identity, info.acl, True))
        self.policy = replace(policy, anchors=(*policy.anchors, *specs))
        self.api.final_creation_available = Mock(return_value=True)
        self.api.create_final = lambda path, acl, directory=False, parent=None: self.api.create(
            path, acl, directory=directory, parent=parent)
        # Separate TEST authority for both kinds of inventory; no real provider.
        self.api.create_inventory = lambda path, acl, parent: self.api.create(path, acl, parent=parent)
        clock = patch.object(observation, "utc_now", return_value=self.base.fixture.reviewed_at + timedelta(seconds=2))
        clock.start()
        self.addCleanup(clock.stop)
        self.fresh()

    def fresh(self):
        self.boundary = native.NativeStoreBoundary(self.policy, self.api)
        self.final = inventory.FinalObjectInventory(self.fixture.protection, self.boundary)
        self.store = self.boundary.mirrored_store()

    def call(self):
        with patch.object(auth, "get_current_process_sid", return_value=self.base.pending.reviewer_sid):
            return service.stage_pending_review(self.base.pending, self.base.fixture.archive,
                self.base.fixture.folder, store=self.store, allowlist_source=self.base.fixture.source,
                restore_store=self.store.primary, complete_registration=True)

    def history_call(self, rid, reason=None):
        with patch.object(auth, "get_current_process_sid", return_value=self.base.pending.reviewer_sid):
            if reason is None:
                return self.store.verify_current(rid, allowlist_source=self.base.fixture.source)
            return self.store.revoke(rid, reason=reason, allowlist_source=self.base.fixture.source)

    def test_registration_restart_and_revocation_preserve_original_bytes(self):
        result = self.call()
        rid = result.completion.registration_id
        self.assertFalse(result.completion.external_eligible)
        original = (self.policy.primary / "registrations" / rid / "registration.json").read_bytes()
        self.fresh()
        self.assertEqual(self.history_call(rid).effective_review_state, "ACCEPTED")
        self.fresh()
        revoked = self.history_call(rid, "Synthetic withdrawal")
        self.fresh()
        self.assertEqual(self.history_call(rid).effective_review_state, "REVOKED")
        self.assertEqual((self.policy.primary / "registrations" / rid / "registration.json").read_bytes(), original)
        self.fresh()
        self.assertEqual(self.history_call(rid, "Repeat").event_id, revoked.event_id)

    def test_missing_authority_blocks_before_gate_or_ce_write(self):
        self.api.final_creation_available.return_value = False
        with self.assertRaises(service.ReviewBlocked):
            self.call()
        self.assertFalse(self.fixture.gate.exists())
        self.assertFalse(any(call[0] == "write" for call in self.api.calls))

    def test_unsealed_complete_copies_are_not_adopted_on_restart(self):
        rid = self.call().completion.registration_id
        for path in self.fixture.protection.root.path.iterdir():
            if path.name.startswith("final-"):
                path.unlink()
        self.fresh()
        with self.assertRaises(native.StagingError):
            self.history_call(rid)
        self.assertTrue(self.fixture.gate.exists())

    def test_readonly_restart_reloads_trust_without_mutation(self):
        rid = self.call().completion.registration_id
        reader = self.fixture.reader()
        result = inventory.inspect_final_history(self.policy, self.fixture.protection,
                                                api=reader, registration_id=rid)
        self.assertEqual(result.reason, "REGISTRATION_HISTORY_VERIFIED_RECHECK_REQUIRED")
        self.assertEqual(result.effective_review_state, "ACCEPTED")
        self.assertFalse(result.valid_registration)
        reader.create.assert_not_called()
        reader.write.assert_not_called()
        reader.mark_delete.assert_not_called()

    def test_no_python_writer_and_duplicate_accepted_does_not_allocate_id(self):
        with patch.object(storage, "_write_exclusive", side_effect=AssertionError("Python write bypass")):
            rid = self.call().completion.registration_id
            self.fresh()
            with patch.object(registration, "uuid4", side_effect=AssertionError("duplicate ID allocation")):
                result = self.call()
        self.assertEqual(result.completion.registration_id, rid)

    def test_production_adapter_never_enables_final_creation(self):
        adapter = object.__new__(windows.Win32StoreNative)
        self.assertFalse(adapter.final_creation_available())
        with self.assertRaises(native.NativeError):
            adapter.create_final()

    def test_wrong_final_acl_prevents_private_bytes_and_retains_gate(self):
        create = self.api.create_final

        def wrong(path, acl, **options):
            handle = create(path, acl, **options)
            if path.name == "registration.json":
                self.api.records[path] = replace(self.api.records[path], acl=self.fixture.fixture.acl)
            return handle

        self.api.create_final = wrong
        with self.assertRaises(service.ReviewBlocked):
            self.call()
        self.assertTrue(self.fixture.gate.exists())
        paths = list((self.policy.primary / "registrations").glob("*/registration.json"))
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0].read_bytes(), b"")

    def test_partial_final_inventory_never_returns_completion_or_repairs(self):
        write = self.api.write

        def partial(handle, raw):
            if handle.name.startswith("final-"):
                handle.write_bytes(raw[:7])
                raise native.NativeError(112)
            write(handle, raw)

        self.api.write = partial
        with self.assertRaises(service.ReviewBlocked):
            self.call()
        self.assertTrue(self.fixture.gate.exists())
        seals = list(self.fixture.protection.root.path.glob("final-*.json"))
        self.assertEqual(len(seals), 1)
        self.assertEqual(seals[0].read_bytes(), seals[0].read_bytes()[:7])
        result = inventory.inspect_final_history(self.policy, self.fixture.protection, api=self.fixture.reader())
        self.assertEqual(result.reason, "REGISTRATION_HISTORY_UNVERIFIED")

    def test_symmetric_object_replacement_is_blocked_by_trusted_ids(self):
        rid = self.call().completion.registration_id
        for root in (self.policy.primary, self.policy.backup):
            path = root / "registrations" / rid / "registration.json"
            self.api.records[path] = replace(self.api.records[path], identity=(1, "f" * 32))
        result = inventory.inspect_final_history(self.policy, self.fixture.protection,
                                                api=self.fixture.reader(), registration_id=rid)
        self.assertEqual(result.reason, "REGISTRATION_HISTORY_UNVERIFIED")

    def test_symmetric_revocation_deletion_remains_blocked_after_restart(self):
        rid = self.call().completion.registration_id
        self.fresh()
        eid = self.history_call(rid, "Withdraw").event_id
        for root in (self.policy.primary, self.policy.backup):
            (root / "registrations" / rid / "revocations" / (eid + ".json")).unlink()
        result = inventory.inspect_final_history(self.policy, self.fixture.protection,
                                                api=self.fixture.reader(), registration_id=rid)
        self.assertEqual(result.reason, "REGISTRATION_HISTORY_UNVERIFIED")

    def test_one_sided_revocation_write_preserves_original_and_gate(self):
        rid = self.call().completion.registration_id
        original = (self.policy.primary / "registrations" / rid / "registration.json").read_bytes()
        self.fresh()
        write = self.api.write

        def fail(handle, raw):
            if handle.name.startswith("REV-OBS-") and handle.is_relative_to(self.policy.backup):
                handle.write_bytes(raw[:5])
                raise native.NativeError(112)
            write(handle, raw)

        self.api.write = fail
        with self.assertRaises(native.StagingError):
            self.history_call(rid, "Withdraw")
        self.assertTrue(self.fixture.gate.exists())
        self.assertEqual((self.policy.primary / "registrations" / rid / "registration.json").read_bytes(), original)
        self.assertFalse(list(self.fixture.protection.root.path.glob("final-REV-*.json")))

    def test_hold_supersession_preserves_both_sealed_histories(self):
        self.base.pending = replace(self.base.pending, review_result="HOLD", decision_reason="Needs review")
        first = self.call().completion.registration_id
        old = {path: path.read_bytes() for root in (self.policy.primary, self.policy.backup)
               for path in (root / "registrations" / first).iterdir()}
        self.base.pending = replace(self.base.pending, review_result="ACCEPTED", decision_reason="",
            reviewed_at_utc=observation.utc_now().isoformat().replace("+00:00", "Z"))
        self.fresh()
        second = self.call().completion.registration_id
        self.assertNotEqual(first, second)
        value = json.loads((self.policy.primary / "registrations" / second / "registration.json").read_bytes())
        self.assertEqual(value["supersedes_registration_id"], first)
        self.assertEqual({path: path.read_bytes() for path in old}, old)
        observed = inventory.inspect_final_history(self.policy, self.fixture.protection,
            api=self.fixture.reader(), registration_id=second)
        self.assertEqual(observed.effective_review_state, "ACCEPTED")

    def test_changed_final_hash_and_unknown_members_block_readonly_restart(self):
        rid = self.call().completion.registration_id
        path = self.policy.primary / "registrations" / rid / "index.json"
        raw = path.read_bytes()
        path.write_bytes(b"changed")
        self.assertEqual(inventory.inspect_final_history(self.policy, self.fixture.protection,
            api=self.fixture.reader()).reason, "REGISTRATION_HISTORY_UNVERIFIED")
        path.write_bytes(raw)
        (path.parent / "unexpected.partial").write_bytes(b"preserve")
        self.assertEqual(inventory.inspect_final_history(self.policy, self.fixture.protection,
            api=self.fixture.reader()).reason, "REGISTRATION_HISTORY_UNVERIFIED")

    def test_gate_release_failure_suppresses_sealed_registration_result(self):
        self.api.bad_release = True
        with self.assertRaises(service.ReviewBlocked):
            self.call()
        self.assertTrue(self.fixture.gate.exists())
        self.assertEqual(len(list(self.fixture.protection.root.path.glob("final-REG-*.json"))), 1)

    def test_final_inventory_strict_fields_and_types(self):
        self.call()
        path = next(self.fixture.protection.root.path.glob("final-REG-*.json"))
        raw = path.read_bytes()
        bad = [raw[:9], raw + b" ", raw.replace(b"{", b'{"schema":"duplicate",', 1)]
        for change in ("extra", "missing", "identity", "acl", "duplicate_object", "hold_schema"):
            value = json.loads(raw)
            if change == "extra":
                value["extra"] = True
            elif change == "missing":
                value["objects"].pop()
            elif change == "identity":
                value["objects"][0]["identity"][0] = True
            elif change == "acl":
                value["objects"][0]["acl"]["aces"][0][0] = False
            elif change == "duplicate_object":
                value["objects"][1] = value["objects"][0]
            else:
                value["schema"] = inventory.SCHEMA
            bad.append(observation.canonical_bytes(value))
        for value in bad:
            with self.subTest(size=len(value)), self.assertRaises(native.StagingError):
                self.final._decode(value, path.name)

    def test_inventory_creation_failure_before_gate_and_no_python_fallback(self):
        self.api.inventory_creation_available.return_value = False
        with self.assertRaises(service.ReviewBlocked):
            self.call()
        self.assertFalse(self.fixture.gate.exists())
        self.assertFalse(any(call[0] == "write" for call in self.api.calls))

    def test_inventory_from_another_boundary_blocks_before_gate(self):
        other = native.NativeStoreBoundary(self.policy, self.api)
        other.final_inventory = self.final
        self.store = other.mirrored_store()
        with self.assertRaises(service.ReviewBlocked):
            self.call()
        self.assertFalse(self.fixture.gate.exists())
        self.assertFalse(any(call[0] == "write" for call in self.api.calls))


if __name__ == "__main__":
    unittest.main()
