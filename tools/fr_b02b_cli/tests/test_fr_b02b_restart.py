"""Fresh-instance restart inspection: temporary files and Native facts doubles."""

from dataclasses import replace
from pathlib import Path
import json
from unittest.mock import Mock, patch
import unittest

import fr_b02b_native_store as native
import fr_b02b_observation as observation
import fr_b02b_restart as restart
import test_fr_b02b_native_store as fixtures


class DiskView:
    """Reconstruct current identities from disk, not a previous writer's pins."""
    allow_changes = False

    def __init__(self, policy, folder):
        self.policy, self.folder = policy, folder
        self.opened, self.closed = [], []
        self.acl_overrides, self.identity_overrides = {}, {}
        self.create = Mock(side_effect=AssertionError("restart mutation forbidden"))
        self.write = Mock(side_effect=AssertionError("restart mutation forbidden"))
        self.mark_delete = Mock(side_effect=AssertionError("restart mutation forbidden"))

    def known_folder(self):
        return self.folder

    def sid(self):
        return self.policy.reviewer_sid

    def open_existing(self, path, directory, content=False):
        if not path.exists():
            raise native.NativeError(2)
        self.opened.append(path)
        return path

    def info(self, path):
        stat = path.lstat()
        acl = next((item.acl for item in self.policy.anchors if item.path == path),
                   self.policy.staging_acl if path.is_dir() else self.policy.file_acl)
        return native.ObjectInfo(path, self.identity_overrides.get(path, (1, f"{stat.st_ino:032x}")),
                                 self.acl_overrides.get(path, acl), path.is_dir(), path.is_symlink(), stat.st_nlink)

    def volume(self, handle):
        return self.policy.primary_volume if handle == self.policy.primary else self.policy.backup_volume

    def exists(self, path):
        try:
            path.lstat()
            return True
        except FileNotFoundError:
            return False

    def children(self, handle):
        return tuple(path.name for path in handle.iterdir())

    def read(self, handle, limit):
        with handle.open("rb") as stream:
            return stream.read(limit)

    def close(self, handle):
        self.closed.append(handle)


class RestartTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.NativeBoundaryTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        policy = self.fixture.policy
        self.policy = replace(policy, anchors=tuple(
            replace(spec, identity=(1, f"{spec.path.lstat().st_ino:032x}")) for spec in policy.anchors))
        self.gate = self.policy.control / "global.gate"

    def view(self):
        return DiskView(self.policy, self.fixture.api.folder)

    def scan(self, inventory=None, api=None):
        api = self.view() if api is None else api
        out = restart.inspect_restart(self.policy, api=api, expected_objects=inventory)
        api.create.assert_not_called()
        api.write.assert_not_called()
        api.mark_delete.assert_not_called()
        self.assertFalse(out.valid_registration)
        self.assertEqual(out.publish_authorization, "NONE")
        return out

    def stage(self, restore=False):
        base = self.fixture.base
        event = base.pending.local_evidence_id
        files = {"a1_archive.zip": base.pending.evidence.a1_snapshot.archive_bytes,
                 "observation.json": base.pending.evidence.record_bytes,
                 "index.json": base.pending.evidence.index_bytes,
                 "pending_review.json": base.metadata()}
        folders = [root / (".review-staging-" + event) for root in (self.policy.primary, self.policy.backup)]
        if restore:
            folders.append(self.policy.primary / (".review-restore-" + event))
        inventory = []
        for folder in folders:
            folder.mkdir()
            for name, raw in files.items():
                (folder / name).write_bytes(raw)
            for path in (folder, *folder.iterdir()):
                stat = path.lstat()
                inventory.append(native.ApprovedObject(
                    path, (1, f"{stat.st_ino:032x}"),
                    self.policy.staging_acl if path.is_dir() else self.policy.file_acl,
                    path.is_dir(), None if path.is_dir() else observation.digest(path.read_bytes())))
        return tuple(inventory), folders

    def test_empty_initial_state_allows_new_attempt_consideration_only(self):
        out = self.scan()
        self.assertEqual(out.classification, "INITIAL_EMPTY")
        self.assertTrue(out.may_attempt_new_work)
        self.assertTrue(out.requires_gate_recheck)
        self.assertEqual(out.gate_status, "ABSENT_OBSERVED")

    def test_invalid_empty_inventory_cannot_approve_clean_state(self):
        self.assertEqual(self.scan([]).reason, "INVALID_TRUSTED_INVENTORY")

    def test_gate_residue_is_never_opened_acquired_or_deleted(self):
        self.gate.write_bytes(b"preserve stale gate")
        api = self.view()
        out = self.scan(api=api)
        self.assertEqual(out.reason, "GATE_PRESENT")
        self.assertEqual(out.inspection_scope, "ANCHORS_ONLY")
        self.assertNotIn(self.gate, api.opened)
        self.assertEqual(self.gate.read_bytes(), b"preserve stale gate")

    def test_gate_cannot_be_opened_as_an_approved_bootstrap_anchor(self):
        self.gate.write_bytes(b"must not open")
        acl = next(spec.acl for spec in self.policy.anchors if not spec.directory)
        spec = native.ApprovedObject(self.gate, (1, f"{self.gate.lstat().st_ino:032x}"), acl,
                                     False, observation.digest(self.gate.read_bytes()))
        self.policy = replace(self.policy, anchors=(*self.policy.anchors, spec))
        api = self.view()
        self.scan(api=api)
        self.assertFalse(self.gate in api.opened)

    def test_approved_control_bootstrap_file_does_not_block_empty_store(self):
        path = self.policy.control / "bootstrap.private.json"
        path.write_bytes(b'{"synthetic":true}')
        acl = next(spec.acl for spec in self.policy.anchors if not spec.directory)
        spec = native.ApprovedObject(path, (1, f"{path.lstat().st_ino:032x}"), acl,
                                     False, observation.digest(path.read_bytes()))
        self.policy = replace(self.policy, anchors=(*self.policy.anchors, spec))
        self.assertEqual(self.scan().classification, "INITIAL_EMPTY")

    def test_complete_hold_and_restore_residue_never_become_valid_registration(self):
        inventory, folders = self.stage(restore=True)
        before = {p: p.read_bytes() for folder in folders for p in folder.iterdir()}
        out = self.scan(inventory)
        self.assertEqual(out.reason, "UNCOMPLETED_HOLD")
        self.assertEqual(out.inspection_scope, "CONTENT_VERIFIED")
        self.assertFalse(out.may_attempt_new_work)
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_new_instances_need_independently_supplied_inventory(self):
        inventory, _ = self.stage()
        self.assertEqual(self.scan().reason, "TRUSTED_INVENTORY_REQUIRED")
        first = self.scan(inventory)
        second = self.scan(tuple(replace(item) for item in inventory))
        self.assertEqual(first, second)
        self.assertEqual(second.reason, "UNCOMPLETED_HOLD")

    def test_one_sided_and_missing_files_remain_hold(self):
        inventory, folders = self.stage()
        missing = folders[1] / "index.json"
        missing.unlink()  # Fixture fault, never inspector cleanup.
        out = self.scan(inventory)
        self.assertEqual(out.classification, "HOLD")
        self.assertFalse(out.may_attempt_new_work)

    def test_one_sided_directory_and_restore_only_residue_block(self):
        event = self.fixture.base.pending.local_evidence_id
        folder = self.policy.primary / (".review-restore-" + event)
        folder.mkdir()
        self.assertEqual(self.scan().reason, "PARTIAL_CE_STAGING")

    def test_fresh_inventory_deserialization_works_without_writer_memory(self):
        inventory, _ = self.stage()
        document = self.fixture.api.folder / "synthetic-test-inventory.json"
        document.write_text(json.dumps([
            {"path": str(spec.path), "identity": spec.identity,
             "directory": spec.directory, "sha256": spec.sha256} for spec in inventory]), encoding="utf-8")
        # Test-only trusted loader. The production private loader is NOT supplied.
        loaded = tuple(native.ApprovedObject(
            Path(row["path"]), tuple(row["identity"]),
            self.policy.staging_acl if row["directory"] else self.policy.file_acl,
            row["directory"], row["sha256"]) for row in json.loads(document.read_text(encoding="utf-8")))
        self.fixture.api.records.clear()
        self.fixture.boundary.pins.clear()
        self.assertEqual(self.scan(loaded).reason, "UNCOMPLETED_HOLD")

    def test_changed_bytes_acl_or_object_identity_are_blocked(self):
        inventory, folders = self.stage()
        target = folders[1] / "index.json"
        original = target.read_bytes()
        target.write_bytes(original + b"changed")
        self.assertEqual(self.scan(inventory).reason, "BYTE_HASH_MISMATCH")
        target.write_bytes(original)
        for kind in ("acl", "identity"):
            api = self.view()
            if kind == "acl":
                api.acl_overrides[target] = replace(self.policy.file_acl, control=4)
            else:
                api.identity_overrides[target] = (1, "f" * 32)
            with self.subTest(kind=kind):
                self.assertEqual(self.scan(inventory, api).reason, "OBJECT_POLICY_MISMATCH")

    def test_unexpected_completion_marker_is_not_a_valid_registration(self):
        inventory, folders = self.stage()
        (folders[0] / "registration_complete.json").write_bytes(b'{}')
        self.assertEqual(self.scan(inventory).reason, "UNSUPPORTED_COMPLETION")

    def test_root_identity_change_and_unreadable_gate_never_report_empty(self):
        api = self.view()
        api.identity_overrides[self.policy.primary] = (1, "f" * 32)
        self.assertEqual(self.scan(api=api).classification, "HOLD")
        api = self.view()
        api.exists = Mock(side_effect=native.NativeError(5))
        out = self.scan(api=api)
        self.assertEqual(out.gate_status, "UNKNOWN")
        self.assertEqual(out.reason, "ACCESS_DENIED")

    def test_only_one_ce_directory_is_not_clean_initial_state(self):
        event = self.fixture.base.pending.local_evidence_id
        (self.policy.primary / (".review-staging-" + event)).mkdir()
        self.assertEqual(self.scan().reason, "PARTIAL_CE_STAGING")

    def test_expected_history_missing_from_empty_roots_is_not_clean(self):
        folder = self.policy.primary / (".review-staging-" + self.fixture.base.pending.local_evidence_id)
        expected = (native.ApprovedObject(folder, (1, "a" * 32), self.policy.staging_acl, True),)
        self.assertEqual(self.scan(expected).reason, "INVENTORY_OBJECTS_MISSING")

    def test_metadata_link_is_revalidated_even_when_trusted_hashes_match(self):
        inventory, folders = self.stage()
        changed = set()
        for folder in folders:
            path = folder / "pending_review.json"
            value = json.loads(path.read_bytes())
            value["local_evidence_id"] = "LOCAL-OBS-" + "f" * 32
            path.write_bytes(observation.canonical_bytes(value))
            changed.add(path)
        inventory = tuple(replace(spec, sha256=observation.digest(spec.path.read_bytes()))
                          if spec.path in changed else spec for spec in inventory)
        self.assertEqual(self.scan(inventory).reason, "INVALID_STORED_LINKS")

    def test_individually_consistent_but_different_ce_decisions_are_not_accepted(self):
        inventory, folders = self.stage()
        path = folders[1] / "pending_review.json"
        value = json.loads(path.read_bytes())
        value["decision_reason"] = "different synthetic decision"
        path.write_bytes(observation.canonical_bytes(value))
        inventory = tuple(replace(spec, sha256=observation.digest(path.read_bytes()))
                          if spec.path == path else spec for spec in inventory)
        self.assertEqual(self.scan(inventory).reason, "CE_RESTORE_BYTES_MISMATCH")

    def test_sharing_and_close_failure_do_not_return_clean_permission(self):
        inventory, folders = self.stage()
        api = self.view()
        opening = api.open_existing

        def sharing(path, directory, content=False):
            if path == folders[0] / "a1_archive.zip":
                raise native.NativeError(32)
            return opening(path, directory, content)

        api.open_existing = sharing
        self.assertEqual(self.scan(inventory, api).reason, "SHARING_BLOCKED")
        self.assertEqual(len(api.closed), len(api.opened))
        api = self.view()
        api.close = Mock(side_effect=native.NativeError(6))
        out = self.scan(inventory, api)
        self.assertEqual(out.classification, "HOLD")
        self.assertFalse(out.may_attempt_new_work)

    def test_missing_policy_and_write_capability_fail_without_native_writes(self):
        with patch("fr_b02b_windows_store.Win32StoreNative", side_effect=AssertionError("DLL forbidden")):
            self.assertEqual(restart.inspect_restart().classification, "HOLD")
        api = self.view()
        api.allow_changes = True
        self.assertEqual(self.scan(api=api).reason, "READ_ONLY_CAPABILITY_REQUIRED")
        self.assertFalse(api.opened)

    def test_native_errors_never_echo_private_details(self):
        api = self.view()
        api.children = Mock(side_effect=OSError("private SID SDDL path must not escape"))
        out = self.scan(api=api)
        self.assertNotIn("private", repr(out))
        self.assertNotIn(self.policy.reviewer_sid, repr(out))

    def test_gate_arriving_during_scan_is_hold_without_content_probe(self):
        api = self.view()
        children = api.children

        def racing(handle):
            names = children(handle)
            self.gate.write_bytes(b"another attempt")
            return names
        api.children = racing
        out = self.scan(api=api)
        self.assertEqual(out.reason, "GATE_PRESENT")
        self.assertEqual(self.gate.read_bytes(), b"another attempt")

    def test_lost_inventory_objects_and_suspected_duplicate_history_block_reentry(self):
        inventory, _ = self.stage()
        extra = self.policy.primary / ".review-staging-LOCAL-OBS-00000000000000000000000000000000"
        extra.mkdir()
        for _ in range(2):
            out = self.scan(inventory)
            self.assertEqual(out.classification, "HOLD")
            self.assertFalse(out.may_attempt_new_work)
        self.assertTrue(extra.exists())


if __name__ == "__main__":
    unittest.main()
