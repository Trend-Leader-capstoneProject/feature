"""Frozen manifest/completion contract: temporary files and ACL/Gate doubles."""

from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
import json
from unittest.mock import Mock, patch
import unittest
from uuid import UUID

import fr_b02b_registration as registration
import fr_b02b_observation as observation
import fr_b02b_protected_store as storage
import fr_b02b_review_service as service
import fr_b02b_windows_auth as auth
import test_fr_b02b_restore as restoring
import test_fr_b02b_native_store as native_fixtures

RID = "REG-OBS-1234567812344234a234123456789abc"


class RegistrationCoreTests(unittest.TestCase):
    def setUp(self):
        self.fixture = restoring.RestoreTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.base = self.fixture.fixture.base
        self.mirror = self.fixture.fixture.store
        self.stores = (self.mirror.primary, self.mirror.backup)
        self.now = self.base.fixture.reviewed_at + timedelta(seconds=2)
        self.clock = patch.object(observation, "utc_now", return_value=self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.uuid = patch.object(registration, "uuid4", return_value=UUID(RID.removeprefix("REG-OBS-")))
        self.uuid.start()
        self.addCleanup(self.uuid.stop)
        for store in self.stores:
            (store.root / "registrations").mkdir()
        self.folders = tuple(store.root / "registrations" / RID for store in self.stores)

    def manifest(self):
        return registration.build_manifest(self.base.pending.evidence, self.base.metadata())

    def test_standalone_preflight_and_finish_share_one_gate_and_release_before_return(self):
        events = []
        fixture = self.fixture.fixture
        preflight = registration.RegistrationCore.preflight
        finish = registration.RegistrationCore.finish

        @contextmanager
        def gate():
            events.append("acquire")
            with fixture.exclusive_section():
                yield
                events.append("release")

        def checked_preflight(core, *args, **kwargs):
            self.assertTrue(fixture.locked)
            events.append("preflight")
            return preflight(core, *args, **kwargs)

        def checked_finish(core, *args, **kwargs):
            self.assertTrue(fixture.locked)
            events.append("finish")
            return finish(core, *args, **kwargs)

        self.mirror.exclusive_section = gate
        with patch.object(registration.RegistrationCore, "preflight", checked_preflight), \
                patch.object(registration.RegistrationCore, "finish", checked_finish):
            result = self.call()
        events.append("returned")
        self.assertEqual(events, ["acquire", "preflight", "finish", "release", "returned"])
        self.assertTrue(result.completion.copies_complete)
        self.assertFalse(fixture.locked)

    def call(self):
        with patch.object(auth, "get_current_process_sid", return_value=self.base.pending.reviewer_sid):
            return service.stage_pending_review(
                self.base.pending, self.base.fixture.archive, self.base.fixture.folder,
                store=self.mirror, allowlist_source=self.base.fixture.source,
                restore_store=self.fixture.target, complete_registration=True)

    def test_frozen_schema_roundtrip_and_complete_both_copies_inside_gate(self):
        original = self.base.originals()
        writer = storage._write_exclusive
        writes = []

        def write(path, raw):
            self.assertTrue(self.fixture.fixture.locked)
            writes.append(path)
            if path.name == "registration_complete.json":
                for folder in self.folders:
                    self.assertTrue((folder / "registration.json").exists())
            writer(path, raw)

        with patch.object(storage, "_write_exclusive", side_effect=write):
            result = self.call()
        completion = result.completion
        self.assertTrue(completion.copies_complete)
        self.assertFalse(completion.external_eligible)
        self.assertEqual(completion.publish_authorization, "NONE")
        self.assertEqual(result.state, "HOLD")
        self.assertEqual(completion.registration_id, RID)
        raw = (self.folders[0] / "registration.json").read_bytes()
        data = registration.validate_manifest(raw, self.base.pending.evidence, self.base.metadata())
        self.assertEqual(len(data), 23)
        self.assertEqual(data["observer_ref"], "UNVERIFIED_LOCAL_OPERATOR")
        self.assertEqual(data["actor_assurance"], "UNVERIFIED")
        self.assertIsNone(data["supersedes_registration_id"])
        self.assertEqual(self.base.originals(), original)
        for folder in self.folders:
            self.assertEqual({p.name for p in folder.iterdir()}, set(registration.REGISTRATION_FILES))
        self.assertEqual((self.folders[0] / "registration_complete.json").read_bytes(),
                         (self.folders[1] / "registration_complete.json").read_bytes())
        self.assertEqual(sum(path.name == "registration_complete.json" for path in writes), 2)

    def test_manifest_missing_extra_duplicate_key_types_and_noncanonical_are_rejected(self):
        raw = self.manifest()
        data = json.loads(raw)
        bad = [raw + b"\n", json.dumps(data, indent=2).encode(),
               raw.replace(b'{', b'{"schema":"FR_B02B_PROTECTED_REVIEW_V1",', 1)]
        for key, replacement in (("schema", None), ("reviewer_sid", 12),
                                 ("index_sha256", "sha256:" + "f" * 64),
                                 ("registration_id", "REG-OBS-" + "0" * 32),
                                 ("publish_authorization", "YES")):
            value = dict(data)
            value[key] = replacement
            bad.append(observation.canonical_bytes(value))
        value = dict(data)
        value.pop("source_url")
        bad.append(observation.canonical_bytes(value))
        value = dict(data, unexpected="value")
        bad.append(observation.canonical_bytes(value))
        for value in bad:
            with self.subTest(size=len(value)), self.assertRaises(storage.StagingError):
                registration.validate_manifest(value, self.base.pending.evidence, self.base.metadata())

    def test_clock_order_future_naive_and_preserved_original_fields(self):
        data = json.loads(self.manifest())
        for field, value in (("reviewed_at_utc", "2026-01-01T00:00:00Z"),
                             ("registration_recorded_at_utc", "2026-01-01T00:00:00Z"),
                             ("registration_recorded_at_utc", "2099-01-01T00:00:00Z"),
                             ("registration_recorded_at_utc", "2026-11-11T00:00:00"),
                             ("confirmed_at_utc", "2026-01-01T00:00:00Z")):
            invalid = dict(data)
            invalid[field] = value
            with self.subTest(field=field), self.assertRaises(storage.StagingError):
                registration.validate_manifest(observation.canonical_bytes(invalid),
                                                self.base.pending.evidence, self.base.metadata())

    def test_marker_schema_and_manifest_hash_are_strict(self):
        raw = self.manifest()
        marker = registration.build_complete_marker(raw, self.base.pending.evidence, self.base.metadata())
        self.assertEqual(len(json.loads(marker)), 4)
        data = json.loads(marker)
        data["registration_sha256"] = "sha256:" + "0" * 64
        with self.assertRaises(storage.StagingError):
            registration.validate_complete_marker(observation.canonical_bytes(data), raw,
                                                  self.base.pending.evidence, self.base.metadata())

    def test_partial_second_marker_keeps_first_and_never_returns_completion(self):
        writer = storage._write_exclusive

        def partial(path, raw):
            if path == self.folders[1] / "registration_complete.json":
                writer(path, raw[:5])
                raise OSError("synthetic marker failure")
            writer(path, raw)

        with patch.object(storage, "_write_exclusive", side_effect=partial):
            with self.assertRaises(service.ReviewBlocked):
                self.call()
        self.assertTrue((self.folders[0] / "registration_complete.json").exists())
        self.assertEqual((self.folders[1] / "registration_complete.json").read_bytes(), b'{"reg')
        self.assertEqual(self.base.originals()[self.base.fixture.archive],
                         self.base.pending.evidence.a1_snapshot.archive_bytes)

    def test_ce_manifest_mismatch_blocks_before_markers(self):
        writer = storage._write_exclusive

        def mismatch(path, raw):
            writer(path, raw)
            if path == self.folders[1] / "registration.json":
                path.write_bytes(raw + b"changed")

        with patch.object(storage, "_write_exclusive", side_effect=mismatch):
            with self.assertRaises(service.ReviewBlocked):
                self.call()
        self.assertFalse(any((p / "registration_complete.json").exists() for p in self.folders))

    def test_existing_registration_collision_never_overwrites_or_retries_id(self):
        self.folders[1].mkdir()
        (self.folders[1] / "sentinel").write_bytes(b"preserve")
        with self.assertRaises(service.ReviewBlocked):
            self.call()
        self.assertFalse(self.folders[0].exists())
        self.assertEqual((self.folders[1] / "sentinel").read_bytes(), b"preserve")
        self.assertEqual(registration.uuid4.call_count, 0)  # Reject unverified history before allocating.

    def test_gate_release_failure_cannot_return_internal_completion(self):
        @contextmanager
        def failure():
            with self.fixture.fixture.exclusive_section():
                yield
            raise OSError("synthetic release failure")
        self.mirror.exclusive_section = failure
        with self.assertRaises(service.ReviewBlocked):
            self.call()
        self.assertTrue(all((p / "registration_complete.json").exists() for p in self.folders))

    def test_explicit_hold_and_rejected_decisions_are_preserved_in_manifest(self):
        for decision in ("HOLD", "REJECTED"):
            self.base.pending = replace(self.base.pending, review_result=decision, decision_reason="synthetic reason")
            value = registration.validate_manifest(self.manifest(), self.base.pending.evidence, self.base.metadata())
            self.assertEqual(value["review_result"], decision)
            self.assertEqual(value["decision_reason"], "synthetic reason")

    def test_missing_or_disagreeing_markers_never_verify_from_files(self):
        self.call()
        path = self.folders[1] / "registration_complete.json"
        path.unlink()  # Temporary fixture fault, not Core cleanup.
        with self.assertRaises(storage.StagingError):
            registration.verify_registration_copies(self.stores, self.folders,
                self.base.pending.evidence, self.base.metadata(), revalidate_input=Mock())
        value = json.loads((self.folders[0] / "registration_complete.json").read_bytes())
        value["registration_id"] = "REG-OBS-ffffffffffff4fffafffffffffffffff"
        path.write_bytes(observation.canonical_bytes(value))
        with self.assertRaises(storage.StagingError):
            registration.verify_registration_copies(self.stores, self.folders,
                self.base.pending.evidence, self.base.metadata(), revalidate_input=Mock())

    def test_same_copy_twice_cannot_prove_ce_completion(self):
        self.call()
        with self.assertRaises(storage.StagingError):
            registration.verify_registration_copies((self.stores[0], self.stores[0]),
                (self.folders[0], self.folders[0]), self.base.pending.evidence, self.base.metadata(),
                revalidate_input=Mock())

    def test_manifest_and_markers_must_bind_to_registration_directory_id(self):
        self.call()
        for folder in self.folders:
            value = json.loads((folder / "registration.json").read_bytes())
            value["registration_id"] = "REG-OBS-ffffffffffff4fffafffffffffffffff"
            raw = observation.canonical_bytes(value)
            (folder / "registration.json").write_bytes(raw)
            (folder / "registration_complete.json").write_bytes(registration.build_complete_marker(
                raw, self.base.pending.evidence, self.base.metadata()))
        with self.assertRaises(storage.StagingError):
            registration.verify_registration_copies(self.stores, self.folders,
                self.base.pending.evidence, self.base.metadata(), revalidate_input=Mock())

    def test_copy_changed_after_other_copy_read_is_detected(self):
        self.call()
        read = self.stores[1]._read_copy

        def change(path, limit):
            raw = read(path, limit)
            if path.name == "registration_complete.json":
                (self.folders[0] / "index.json").write_bytes(b"changed after first read")
            return raw

        with patch.object(self.stores[1], "_read_copy", side_effect=change):
            with self.assertRaises(storage.StagingError):
                registration.verify_registration_copies(self.stores, self.folders,
                    self.base.pending.evidence, self.base.metadata(), revalidate_input=Mock())

    def test_unverified_supersession_history_blocks_without_creation(self):
        data = json.loads(self.manifest())
        data["supersedes_registration_id"] = "REG-OBS-ffffffffffff4fffafffffffffffffff"
        raw = observation.canonical_bytes(data)
        registration.validate_manifest(raw, self.base.pending.evidence, self.base.metadata())
        with self.assertRaises(storage.StagingError):
            registration.RegistrationCore(raw, self.base.pending.evidence, self.base.metadata())
        self.assertFalse(any(folder.exists() for folder in self.folders))

    def test_gate_acquisition_and_permission_failure_never_write_markers(self):
        @contextmanager
        def blocked():
            raise OSError("synthetic Gate denial")
            yield
        self.mirror.exclusive_section = blocked
        with self.assertRaises(service.ReviewBlocked):
            self.call()
        self.assertFalse(any(folder.exists() for folder in self.folders))

    def test_current_native_and_hold_inventory_are_not_final_completion_proof(self):
        fixture = native_fixtures.NativeBoundaryTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        raw = registration.build_manifest(fixture.base.pending.evidence, fixture.base.metadata())
        core = registration.RegistrationCore(raw, fixture.base.pending.evidence, fixture.base.metadata())
        with self.assertRaises(storage.StagingError):
            core.require_environment((fixture.store.primary, fixture.store.backup), fixture.store.primary,
                                      fixture.base.pending.evidence, fixture.base.metadata())
        self.assertFalse(fixture.api.calls)


if __name__ == "__main__":
    unittest.main()
