"""Isolated temporary I/O; protection, independent disks and Gate are doubles."""

from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import Mock, patch
import unittest

import fr_b02b_observation as observation
import fr_b02b_protected_store as storage
import fr_b02b_review_service as service
import test_fr_b02b_protected_store as single


class MirroredStoreTests(unittest.TestCase):
    def setUp(self):
        self.base = single.ProtectedStoreTests()
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.backup_root = self.base.fixture.root / "backup-area"
        self.backup_root.mkdir()
        self.backup = storage.ProtectedEvidenceStore(self.backup_root, Mock(return_value=True))
        self.locked = False
        self.layout = Mock(return_value=True)  # Synthetic proof, NOT real disk/ACL verification.
        self.store = storage.MirroredEvidenceStore(
            self.base.store, self.backup, verify_layout=self.layout,
            exclusive_section=self.exclusive_section)
        self.backup_dir = self.backup_root / self.base.expected_dir.name

    @contextmanager
    def exclusive_section(self):
        self.assertFalse(self.locked)
        self.locked = True
        try:
            yield
        finally:
            self.locked = False

    def stage(self):
        return self.base.stage(store=self.store)

    def expected(self):
        evidence = self.base.pending.evidence
        return {"a1_archive.zip": evidence.a1_snapshot.archive_bytes,
                "observation.json": evidence.record_bytes,
                "index.json": evidence.index_bytes,
                "pending_review.json": self.base.metadata()}

    def test_both_copies_match_original_bytes_and_sha256_but_remain_hold(self):
        before = self.base.originals()
        writer = storage._write_exclusive

        def guarded_write(path, raw):
            self.assertTrue(self.locked)
            writer(path, raw)

        with patch.object(storage, "_write_exclusive", side_effect=guarded_write) as writes:
            result = self.stage()
        self.assertEqual(writes.call_count, 8)
        self.assertEqual(result.state, "HOLD")
        self.assertEqual(result.publish_authorization, "NONE")
        self.assertFalse(hasattr(result, "registration_id"))
        self.assertEqual(result.primary_staging_dir, self.base.expected_dir)
        self.assertEqual(result.backup_staging_dir, self.backup_dir)
        for folder in (result.primary_staging_dir, result.backup_staging_dir):
            self.assertEqual({p.name for p in folder.iterdir()}, set(self.expected()))
            for name, raw in self.expected().items():
                self.assertEqual((folder / name).read_bytes(), raw)
                self.assertEqual(dict(result.sha256)[name], observation.digest(raw))
        self.assertEqual(self.base.originals(), before)
        self.assertFalse(self.locked)

    def test_missing_deployment_dependencies_never_write(self):
        for missing in ("primary", "backup", "verify_layout", "exclusive_section"):
            values = dict(primary=self.base.store, backup=self.backup,
                          verify_layout=self.layout, exclusive_section=self.exclusive_section)
            values[missing] = None
            self.store = storage.MirroredEvidenceStore(**values)
            with self.subTest(missing=missing), self.assertRaises(service.ReviewBlocked):
                self.stage()
            self.assertEqual(list(self.base.root.iterdir()), [])
            self.assertEqual(list(self.backup_root.iterdir()), [])

    def test_backup_collision_blocks_before_primary_creation(self):
        self.backup_dir.mkdir()
        sentinel = self.backup_dir / "untouched.bin"
        sentinel.write_bytes(b"existing")
        with self.assertRaises(service.ReviewBlocked):
            self.stage()
        self.assertFalse(self.base.expected_dir.exists())
        self.assertEqual(sentinel.read_bytes(), b"existing")

    def test_unverified_layout_or_backup_acl_blocks_both_writes(self):
        for problem in (False, OSError("private layout detail"), "acl"):
            self.layout.side_effect = problem if isinstance(problem, Exception) else None
            self.layout.return_value = problem is not False
            self.backup.verify_protection.return_value = problem != "acl"
            with self.subTest(problem=type(problem).__name__), self.assertRaises(service.ReviewBlocked):
                self.stage()
            self.assertFalse(self.base.expected_dir.exists())
            self.assertFalse(self.backup_dir.exists())

    def test_same_or_nested_roots_are_rejected(self):
        for root in (self.base.root, self.base.root / "nested"):
            self.backup.root = root
            with self.subTest(root=root.name), self.assertRaises(service.ReviewBlocked):
                self.stage()
            self.assertFalse(self.base.expected_dir.exists())

    def test_backup_root_overlapping_inputs_is_rejected_by_service(self):
        self.backup.root = self.base.fixture.folder
        with patch.object(self.store, "stage") as stage:
            with self.assertRaises(service.ReviewBlocked):
                self.stage()
            stage.assert_not_called()

    def test_partial_backup_write_keeps_primary_and_partial_without_retry(self):
        writer = storage._write_exclusive
        calls = []

        def partial(path, raw):
            calls.append(path)
            if path.parent == self.backup_dir:
                writer(path, raw[:3])
                raise OSError("private backup failure")
            writer(path, raw)

        with patch.object(storage, "_write_exclusive", side_effect=partial):
            with self.assertRaises(service.ReviewBlocked):
                self.stage()
        self.assertEqual(len(calls), 5)
        self.assertEqual((self.backup_dir / "a1_archive.zip").read_bytes(),
                         self.expected()["a1_archive.zip"][:3])
        for name, raw in self.expected().items():
            self.assertEqual((self.base.expected_dir / name).read_bytes(), raw)
        with self.assertRaises(service.ReviewBlocked):
            self.stage()
        self.assertEqual(len(calls), 5)

    def test_primary_corruption_during_backup_is_detected(self):
        writer = storage._write_exclusive

        def corrupt(path, raw):
            writer(path, raw)
            if path.parent == self.backup_dir:
                (self.base.expected_dir / "index.json").write_bytes(b"changed")

        with patch.object(storage, "_write_exclusive", side_effect=corrupt):
            with self.assertRaises(service.ReviewBlocked):
                self.stage()
        self.assertEqual((self.base.expected_dir / "index.json").read_bytes(), b"changed")

    def test_backup_flush_failure_preserves_written_file_and_primary(self):
        writer = storage._write_exclusive

        def fail_flush(path, raw):
            if path.parent == self.backup_dir:
                with patch.object(storage.os, "fsync", side_effect=OSError("synthetic flush failure")):
                    writer(path, raw)
            else:
                writer(path, raw)

        with patch.object(storage, "_write_exclusive", side_effect=fail_flush):
            with self.assertRaises(service.ReviewBlocked):
                self.stage()
        self.assertEqual((self.backup_dir / "a1_archive.zip").read_bytes(),
                         self.expected()["a1_archive.zip"])
        self.assertEqual({p.name for p in self.base.expected_dir.iterdir()}, set(self.expected()))

    def test_late_backup_file_collision_is_not_overwritten(self):
        writer = storage._write_exclusive

        def collide(path, raw):
            if path.parent == self.backup_dir:
                path.write_bytes(b"existing collision")
            writer(path, raw)

        with patch.object(storage, "_write_exclusive", side_effect=collide):
            with self.assertRaises(service.ReviewBlocked):
                self.stage()
        self.assertEqual((self.backup_dir / "a1_archive.zip").read_bytes(), b"existing collision")

    def test_primary_file_replaced_with_identical_bytes_during_backup_is_detected(self):
        writer = storage._write_exclusive
        preserved = self.base.fixture.root / "preserved-index.json"

        def replace_copy(path, raw):
            writer(path, raw)
            if path.parent == self.backup_dir and not preserved.exists():
                original = self.base.expected_dir / "index.json"
                original.rename(preserved)
                original.write_bytes(preserved.read_bytes())

        with patch.object(storage, "_write_exclusive", side_effect=replace_copy):
            with self.assertRaises(service.ReviewBlocked):
                self.stage()
        self.assertTrue(preserved.exists())

    def test_primary_acl_loss_during_backup_is_detected(self):
        writer = storage._write_exclusive

        def lose_acl(path, raw):
            writer(path, raw)
            if path.parent == self.backup_dir:
                self.base.store.verify_protection.return_value = False

        with patch.object(storage, "_write_exclusive", side_effect=lose_acl):
            with self.assertRaises(service.ReviewBlocked):
                self.stage()
        self.assertTrue(self.base.expected_dir.exists())

    def test_backup_root_replacement_during_primary_write_is_detected(self):
        writer = storage._write_exclusive
        renamed = self.backup_root.with_name("preserved-backup")

        def replace_root(path, raw):
            writer(path, raw)
            if not renamed.exists():
                self.backup_root.rename(renamed)
                self.backup_root.mkdir()

        with patch.object(storage, "_write_exclusive", side_effect=replace_root):
            with self.assertRaises(service.ReviewBlocked):
                self.stage()
        self.assertTrue(renamed.exists())
        self.assertFalse(self.backup_dir.exists())

    def test_backup_configuration_change_cannot_redirect_writes(self):
        writer = storage._write_exclusive
        other_root = self.base.fixture.root / "unapproved-other-root"
        other_root.mkdir()

        def redirect(path, raw):
            writer(path, raw)
            self.backup.root = other_root

        with patch.object(storage, "_write_exclusive", side_effect=redirect):
            with self.assertRaises(service.ReviewBlocked):
                self.stage()
        self.assertFalse(any(other_root.iterdir()))
        self.assertFalse(self.backup_dir.exists())

    def test_input_change_during_backup_is_rejected(self):
        writer = storage._write_exclusive

        def change_input(path, raw):
            writer(path, raw)
            if path.parent == self.backup_dir:
                self.base.fixture.archive.write_bytes(b"changed source")

        with patch.object(storage, "_write_exclusive", side_effect=change_input):
            with self.assertRaises(service.ReviewBlocked):
                self.stage()
        self.assertEqual(self.base.fixture.archive.read_bytes(), b"changed source")

    def test_exclusive_section_release_failure_cannot_return_receipt(self):
        @contextmanager
        def failing_release():
            with self.exclusive_section():
                yield
            raise OSError("private release failure")

        self.store.exclusive_section = failing_release
        with self.assertRaises(service.ReviewBlocked):
            self.stage()
        self.assertTrue(self.base.expected_dir.exists())
        self.assertTrue(self.backup_dir.exists())

    def test_unvalidated_snapshot_is_rejected_before_writing(self):
        forged = replace(self.base.pending.evidence, index_bytes=b"invalid")
        with self.assertRaises(storage.StagingError):
            self.store.stage(forged, self.base.metadata(), revalidate_input=Mock())
        self.assertFalse(self.base.expected_dir.exists())
        self.assertFalse(self.backup_dir.exists())


if __name__ == "__main__":
    unittest.main()
