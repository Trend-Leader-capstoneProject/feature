"""Temporary I/O + Native doubles. No Windows API, operating roots or SYN labs."""

from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import unittest

import fr_b02b_native_store as native
import fr_b02b_protected_store as storage
import fr_b02b_review_service as service
import test_fr_b02b_protected_store as single

SID = "S-1-5-21-100-200-300-1001"


class FakeApi:
    """All Native facts are synthetic, including different-disk claims."""
    allow_changes = True

    def __init__(self, folder):
        self.folder = folder
        self.records, self.volumes, self.closed, self.deleted = {}, {}, [], []
        self.calls, self.current_sid = [], SID
        self.bad_new_acl = self.partial = self.bad_release = False

    def known_folder(self):
        return self.folder

    def sid(self):
        return self.current_sid

    def open_existing(self, path, directory, content=False):
        self.calls.append(("open", path))
        return path

    def info(self, handle):
        return self.records[handle]

    def volume(self, handle):
        return self.volumes[handle]

    def close(self, handle):
        self.closed.append(handle)

    def create(self, path, acl, directory=False, gate=False, parent=None):
        self.calls.append(("create", path))
        if path.exists():
            raise native.NativeError(80)
        if directory:
            path.mkdir()
        else:
            path.touch(exist_ok=False)
        self.records[path] = native.ObjectInfo(
            path, (1, f"{len(self.records) + 100:032x}"), acl, directory, False, 1)
        if self.bad_new_acl:
            self.records[path] = replace(self.records[path], acl=replace(acl, control=4))
        return path

    def write(self, handle, raw):
        self.calls.append(("write", handle))
        handle.write_bytes(raw[:3] if self.partial else raw)
        if self.partial:
            raise native.NativeError(112)

    def flush(self, handle):
        self.calls.append(("flush", handle))

    def read(self, handle, limit):
        return handle.read_bytes()[:limit]

    def mark_delete(self, handle):
        self.calls.append(("delete", handle))
        if self.bad_release:
            raise native.NativeError(5)
        self.deleted.append(handle)
        handle.unlink()


class NativeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.base = single.ProtectedStoreTests()
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        root = self.base.fixture.root
        backup, control, config = (root / name for name in ("backup", "control", "Config"))
        for folder in (backup, control, config):
            folder.mkdir()
        settings = config / "settings.json"
        settings.write_bytes(b'{"synthetic":true}\n')
        self.api = FakeApi(root)
        # ACL masks here are TEST FIXTURES, never production defaults.
        self.acl = native.AclPolicy(SID, ((0, 0, 0x1301BF, SID),), 0x1004)
        paths = set()
        for leaf in (self.base.root, backup, control, settings):
            paths.update((*leaf.parents, leaf))
        specs = []
        for i, path in enumerate(sorted(paths, key=lambda p: (len(p.parts), str(p)))):
            acl = self.acl
            if path in (settings, config):
                acl = native.AclPolicy("S-1-5-32-544", ((0, 0, 0x120089, SID),), 0x1004)
            elif path in (self.base.root, backup, control):
                acl = native.AclPolicy("S-1-5-32-544", ((0, 0, 0x1200AF, SID),), 0x1004)
            info = native.ObjectInfo(path, (1, f"{i + 1:032x}"), acl, path != settings, False, 1)
            self.api.records[path] = info
            specs.append(native.ApprovedObject(path, info.identity, acl, info.directory,
                                               storage.observation.digest(settings.read_bytes())
                                               if path == settings else None))
        self.api.volumes[self.base.root] = native.VolumeInfo("primary-volume", 1, (0,))
        self.api.volumes[backup] = native.VolumeInfo("backup-volume", 1, (1,))
        self.policy = native.StorePolicy(
            SID, tuple(specs), self.base.root, backup, control, "Config",
            self.api.volumes[self.base.root], self.api.volumes[backup],
            self.acl, self.acl, self.acl)
        self.boundary = native.NativeStoreBoundary(self.policy, self.api)
        self.store = self.boundary.mirrored_store()
        self.gate = control / "global.gate"
        self.backup_dir = backup / self.base.expected_dir.name

    def stage(self):
        return self.base.stage(store=self.store)

    def test_mutating_hook_cannot_create_under_config_even_inside_gate(self):
        config = self.api.folder / self.policy.config_relative
        path = config / (".review-staging-" + self.base.pending.local_evidence_id)
        with self.assertRaises(storage.StagingError):
            with self.boundary.exclusive_section():
                try:
                    self.boundary.create_staging(config, path)
                except storage.StagingError:
                    pass  # Caught failures must still poison normal Gate release.
        self.assertFalse(path.exists())
        self.assertTrue(self.gate.exists())

    def test_caught_partial_native_write_still_poisoned_and_keeps_gate(self):
        path = self.base.expected_dir
        with self.assertRaises(storage.StagingError):
            with self.boundary.exclusive_section():
                self.boundary.create_staging(self.policy.primary, path)
                self.api.partial = True
                with self.assertRaises(native.NativeError):
                    self.boundary.write_file(self.policy.primary, path / "index.json", b"synthetic")
        self.assertTrue(self.gate.exists())
        self.assertFalse(self.api.deleted)

    def test_native_mirror_rejects_python_backup_before_native_calls(self):
        self.store.backup = storage.ProtectedEvidenceStore(self.policy.backup, lambda path: True)
        with self.assertRaises(service.ReviewBlocked):
            self.stage()
        self.assertFalse(self.api.calls)

    def test_native_restore_uses_same_boundary_and_gate_without_python_writer(self):
        original = self.store.stage

        def restoring(*args, **kwargs):
            return original(*args, **kwargs, restore_store=self.store.primary)

        with patch.object(self.store, "stage", side_effect=restoring), \
                patch.object(storage, "_write_exclusive", side_effect=AssertionError("Python write bypass")):
            out = self.stage()
        folder = self.policy.primary / (".review-restore-" + self.base.pending.local_evidence_id)
        self.assertEqual(out.restored_staging_dir, folder)
        self.assertEqual(out.state, "HOLD")
        self.assertEqual(len([c for c in self.api.calls if c[0] == "write"]), 12)
        self.assertEqual(self.api.deleted, [self.gate])

    def test_native_partial_restore_retains_gate_and_both_valid_source_copies(self):
        original, write = self.store.stage, self.api.write

        def restoring(*args, **kwargs):
            return original(*args, **kwargs, restore_store=self.store.primary)

        def partial_restore(handle, raw):
            if handle.parent.name.startswith(".review-restore-"):
                self.api.partial = True
            write(handle, raw)

        self.api.write = partial_restore
        with patch.object(self.store, "stage", side_effect=restoring):
            with self.assertRaises(service.ReviewBlocked):
                self.stage()
        self.assertTrue(self.gate.exists())
        self.assertFalse(self.api.deleted)
        for source in (self.base.expected_dir, self.backup_dir):
            self.assertEqual((source / "index.json").read_bytes(), self.base.pending.evidence.index_bytes)
        self.assertTrue(self.boundary.failed)

    def test_native_hooks_keep_core_receipt_hold_and_write_only_after_verification(self):
        with patch.object(storage, "_write_exclusive", side_effect=AssertionError("Python writer forbidden")):
            out = self.stage()
        self.assertEqual(out.state, "HOLD")
        self.assertFalse(hasattr(out, "registration_id"))
        self.assertEqual(len([c for c in self.api.calls if c[0] == "write"]), 8)
        self.assertEqual(self.api.deleted, [self.gate])
        self.assertFalse(self.gate.exists())
        self.assertEqual(len(self.api.closed), len(set(self.api.closed)))

    def test_unconfigured_policy_does_not_instantiate_native(self):
        with patch("fr_b02b_windows_store.Win32StoreNative", side_effect=AssertionError("Native forbidden")):
            with self.assertRaises((storage.StagingError, service.ReviewBlocked)):
                native.build_native_store()

    def test_wrong_sid_or_volume_overlap_or_root_id_blocks_before_gate(self):
        for problem in ("sid", "disks", "identity"):
            with self.subTest(problem=problem):
                if problem == "sid":
                    self.api.current_sid = "S-1-5-21-9-9-9-9"
                elif problem == "disks":
                    self.api.volumes[self.policy.backup] = replace(self.policy.backup_volume, disks=(0,))
                else:
                    self.api.records[self.policy.primary] = replace(
                        self.api.records[self.policy.primary], identity=(1, "f" * 32))
                boundary = native.NativeStoreBoundary(self.policy, self.api)
                with self.assertRaises((storage.StagingError, service.ReviewBlocked)):
                    self.base.stage(store=boundary.mirrored_store())
                self.assertFalse(self.gate.exists())
                self.api.current_sid = SID
                self.api.volumes[self.policy.backup] = self.policy.backup_volume

    def test_unapproved_ancestor_or_known_folder_blocks_without_creation(self):
        for policy in (replace(self.policy, anchors=self.policy.anchors[1:]),
                       replace(self.policy, config_relative="other")):
            with self.subTest(), self.assertRaises((storage.StagingError, service.ReviewBlocked)):
                boundary = native.NativeStoreBoundary(policy, self.api)
                self.base.stage(store=boundary.mirrored_store())
        self.assertFalse(any(c[0] == "create" for c in self.api.calls))

    def test_existing_gate_is_not_opened_reused_or_deleted(self):
        self.gate.write_bytes(b"preserve")
        with self.assertRaises((storage.StagingError, service.ReviewBlocked)):
            self.stage()
        self.assertEqual(self.gate.read_bytes(), b"preserve")
        self.assertFalse(self.api.deleted)
        self.assertFalse(self.base.expected_dir.exists())

    def test_new_object_acl_failure_writes_no_original_bytes_and_keeps_gate(self):
        create = self.api.create

        def reject_file(path, acl, **options):
            handle = create(path, acl, **options)
            if path.name == "a1_archive.zip":
                self.api.records[path] = replace(self.api.records[path], acl=replace(acl, control=4))
            return handle

        self.api.create = reject_file
        with self.assertRaises((storage.StagingError, service.ReviewBlocked)):
            self.stage()
        self.assertFalse(any(c[0] == "write" for c in self.api.calls))
        self.assertEqual((self.base.expected_dir / "a1_archive.zip").read_bytes(), b"")
        self.assertTrue(self.gate.exists())
        self.assertFalse(self.api.deleted)

    def test_partial_write_and_uncertain_attempt_cannot_retry_or_release_gate(self):
        self.api.partial = True
        with self.assertRaises((storage.StagingError, service.ReviewBlocked)):
            self.stage()
        creates = len([c for c in self.api.calls if c[0] == "create"])
        with self.assertRaises((storage.StagingError, service.ReviewBlocked)):
            self.stage()
        self.assertEqual(len([c for c in self.api.calls if c[0] == "create"]), creates)
        self.assertTrue(self.gate.exists())
        self.assertFalse(self.api.deleted)

    def test_acl_or_config_change_during_copy_keeps_gate_and_hold(self):
        write = self.api.write

        def change(handle, raw):
            write(handle, raw)
            self.api.records[self.policy.primary] = replace(
                self.api.records[self.policy.primary], acl=replace(self.acl, control=4))

        self.api.write = change
        with self.assertRaises((storage.StagingError, service.ReviewBlocked)):
            self.stage()
        self.assertTrue(self.gate.exists())
        self.assertFalse(self.api.deleted)

    def test_gate_identity_change_or_release_failure_cannot_return_receipt(self):
        self.api.bad_release = True
        with self.assertRaises((storage.StagingError, service.ReviewBlocked)):
            self.stage()
        self.assertTrue(self.gate.exists())
        self.assertTrue(self.backup_dir.exists())
        self.assertFalse(self.api.deleted)

    def test_configuration_bytes_change_during_backup_keeps_original_change_and_hold(self):
        write = self.api.write
        settings = next(spec.path for spec in self.policy.anchors if not spec.directory)

        def change(handle, raw):
            write(handle, raw)
            if handle.parent == self.backup_dir:
                settings.write_bytes(b"changed private configuration")

        self.api.write = change
        with self.assertRaises(service.ReviewBlocked):
            self.stage()
        self.assertTrue(self.gate.exists())
        self.assertEqual(settings.read_bytes(), b"changed private configuration")
        self.assertFalse(self.api.deleted)

    def test_gate_id_change_is_not_deleted_as_the_acquired_object(self):
        write = self.api.write

        def replace_gate(handle, raw):
            write(handle, raw)
            self.api.records[self.gate] = replace(self.api.records[self.gate], identity=(1, "f" * 32))

        self.api.write = replace_gate
        with self.assertRaises(service.ReviewBlocked):
            self.stage()
        self.assertTrue(self.gate.exists())
        self.assertFalse(self.api.deleted)

    def test_work_handle_close_failure_retains_gate_without_double_close(self):
        close = self.api.close

        def fail_close(handle):
            close(handle)
            if handle.name == "index.json":
                raise native.NativeError(6)

        self.api.close = fail_close
        with self.assertRaises(service.ReviewBlocked):
            self.stage()
        self.assertTrue(self.gate.exists())
        self.assertFalse(self.api.deleted)
        self.assertEqual(len(self.api.closed), len(set(self.api.closed)))

    def test_read_only_capability_and_excessive_new_acl_never_create(self):
        self.api.allow_changes = False
        with self.assertRaises(service.ReviewBlocked):
            self.stage()
        broad = replace(self.acl, aces=((0, 0, 0x1F01FF, SID),))
        with self.assertRaises(storage.StagingError):
            native.NativeStoreBoundary(replace(self.policy, file_acl=broad), self.api)
        self.assertFalse(any(c[0] == "create" for c in self.api.calls))

    def test_rooted_config_relative_path_cannot_escape_known_folder(self):
        for value in (r"\Config", "C:Config", "..\\Config", "."):
            with self.subTest(value=value), self.assertRaises(storage.StagingError):
                native.NativeStoreBoundary(replace(self.policy, config_relative=value), self.api)
        self.assertFalse(self.api.calls)

    def test_reparse_root_and_readable_config_with_unsafe_owner_are_blocked(self):
        initial = self.api.records[self.policy.primary]
        self.api.records[self.policy.primary] = replace(initial, reparse=True)
        with self.assertRaises(service.ReviewBlocked):
            self.stage()
        self.assertFalse(self.gate.exists())
        self.api.records[self.policy.primary] = initial
        specs = tuple(replace(spec, acl=self.acl) if not spec.directory else spec
                      for spec in self.policy.anchors)
        for spec in specs:
            if not spec.directory:
                self.api.records[spec.path] = replace(self.api.records[spec.path], acl=self.acl)
        boundary = native.NativeStoreBoundary(replace(self.policy, anchors=specs), self.api)
        with self.assertRaises(service.ReviewBlocked):
            self.base.stage(store=boundary.mirrored_store())
        self.assertFalse(self.gate.exists())

    def test_private_details_are_not_retained_in_native_failure(self):
        self.assertEqual(native.NativeError(5).args, ("native protected operation failed; HOLD",))
        self.assertNotIn(SID, repr(self.policy))


if __name__ == "__main__":
    unittest.main()
