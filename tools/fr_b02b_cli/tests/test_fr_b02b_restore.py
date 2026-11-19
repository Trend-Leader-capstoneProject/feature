"""Restore round trips in temporary stores. ACL/layout/Gate are doubles only."""

from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import Mock, patch
import unittest

import fr_b02b_protected_store as storage
import fr_b02b_review_service as service
import fr_b02b_windows_auth as windows_auth
import fr_b02b_observation as observation
import fr_b02b_restore as restore
import test_fr_b02b_mirrored_store as mirrored


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.fixture = mirrored.MirroredStoreTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.base.fixture.root / "isolated-restore"
        self.root.mkdir()
        self.target = storage.ProtectedEvidenceStore(self.root, Mock(return_value=True))
        self.folder = self.root / (".review-restore-" + self.fixture.base.pending.local_evidence_id)

    def stage(self):
        return service.stage_pending_review(
            self.fixture.base.pending, self.fixture.base.fixture.archive,
            self.fixture.base.fixture.folder, store=self.fixture.store,
            allowlist_source=self.fixture.base.fixture.source, restore_store=self.target)

    def call(self):
        with patch.object(windows_auth, "get_current_process_sid", return_value=self.fixture.base.pending.reviewer_sid), \
                patch.object(observation, "utc_now",
                             return_value=self.fixture.base.fixture.reviewed_at + timedelta(seconds=1)):
            return self.stage()

    def test_restore_reads_backup_and_round_trips_exact_bytes_under_same_gate(self):
        before = self.fixture.base.originals()
        read = self.fixture.backup._read_copy
        reads = []

        def backup_read(path, limit):
            reads.append(path.name)
            self.assertTrue(self.fixture.locked)
            return read(path, limit)

        self.fixture.backup._read_copy = backup_read
        with patch.object(restore, "_validated_files", wraps=storage._validated_files) as validate:
            result = self.call()
        self.assertEqual(validate.call_count, 2)  # Expected snapshot + rebuilt restored snapshot.
        self.assertIsNot(validate.call_args.args[0], self.fixture.base.pending.evidence)
        self.assertEqual(result.restored_staging_dir, self.folder)
        self.assertEqual((result.state, result.publish_authorization), ("HOLD", "NONE"))
        self.assertFalse(hasattr(result, "registration_id"))
        self.assertEqual({p.name for p in self.folder.iterdir()}, set(self.fixture.expected()))
        for name, raw in self.fixture.expected().items():
            self.assertEqual((self.folder / name).read_bytes(), raw)
            self.assertIn(name, reads)
        self.assertEqual(self.fixture.base.originals(), before)

    def test_target_collision_blocks_before_source_staging_or_overwrite(self):
        self.folder.mkdir()
        (self.folder / "sentinel").write_bytes(b"preserve")
        with self.assertRaises(service.ReviewBlocked):
            self.call()
        self.assertFalse(self.fixture.base.expected_dir.exists())
        self.assertEqual((self.folder / "sentinel").read_bytes(), b"preserve")

    def test_partial_restore_preserves_both_sources_and_partial_without_retry(self):
        writer = storage._write_exclusive

        def partial(path, raw):
            if path.parent == self.folder:
                writer(path, raw[:3])
                raise OSError("private restore failure")
            writer(path, raw)

        with patch.object(storage, "_write_exclusive", side_effect=partial):
            with self.assertRaises(service.ReviewBlocked):
                self.call()
        self.assertEqual((self.folder / "a1_archive.zip").read_bytes(),
                         self.fixture.expected()["a1_archive.zip"][:3])
        for source in (self.fixture.base.expected_dir, self.fixture.backup_dir):
            for name, raw in self.fixture.expected().items():
                self.assertEqual((source / name).read_bytes(), raw)
        with self.assertRaises(service.ReviewBlocked):
            self.call()

    def test_backup_mismatch_before_restore_writes_no_target_files(self):
        read = self.fixture.backup._read_copy
        self.fixture.backup._read_copy = lambda path, limit: b"mismatch" if path.name == "index.json" else read(path, limit)
        with self.assertRaises(service.ReviewBlocked):
            self.call()
        self.assertFalse(self.folder.exists())

    def test_source_change_during_restore_holds_without_repair(self):
        writer = storage._write_exclusive

        def change(path, raw):
            writer(path, raw)
            if path.parent == self.folder:
                (self.fixture.backup_dir / "index.json").write_bytes(b"changed")

        with patch.object(storage, "_write_exclusive", side_effect=change):
            with self.assertRaises(service.ReviewBlocked):
                self.call()
        self.assertEqual((self.fixture.backup_dir / "index.json").read_bytes(), b"changed")

    def test_target_acl_failure_blocks_before_source_writes(self):
        self.target.verify_protection.return_value = False
        with self.assertRaises(service.ReviewBlocked):
            self.call()
        self.assertFalse(self.fixture.base.expected_dir.exists())

    def test_gate_acquisition_failure_never_creates_restore(self):
        @contextmanager
        def failed_acquire():
            raise OSError("synthetic Gate failure")
            yield

        self.fixture.store.exclusive_section = failed_acquire
        with self.assertRaises(service.ReviewBlocked):
            self.call()
        self.assertFalse(self.folder.exists())

    def test_gate_release_failure_never_returns_verified_restore_receipt(self):
        @contextmanager
        def failed_release():
            with self.fixture.exclusive_section():
                yield
            raise OSError("synthetic Gate release failure")

        self.fixture.store.exclusive_section = failed_release
        with self.assertRaises(service.ReviewBlocked):
            self.call()
        self.assertEqual({p.name for p in self.folder.iterdir()}, set(self.fixture.expected()))

    def test_extra_restore_file_is_preserved_but_not_accepted(self):
        writer = storage._write_exclusive

        def extra(path, raw):
            writer(path, raw)
            if path.parent == self.folder:
                (self.folder / "unexpected.json").write_bytes(b"preserve")

        with patch.object(storage, "_write_exclusive", side_effect=extra):
            with self.assertRaises(service.ReviewBlocked):
                self.call()
        self.assertEqual((self.folder / "unexpected.json").read_bytes(), b"preserve")

    def test_restore_metadata_corruption_never_repairs_or_accepts(self):
        writer = storage._write_exclusive

        def corrupt(path, raw):
            writer(path, raw)
            if path.parent == self.folder and path.name == "pending_review.json":
                path.write_bytes(raw.replace(b'ACCEPTED', b'REJECTED'))

        with patch.object(storage, "_write_exclusive", side_effect=corrupt):
            with self.assertRaises(service.ReviewBlocked):
                self.call()
        self.assertIn(b"REJECTED", (self.folder / "pending_review.json").read_bytes())

    def test_restore_target_cannot_overlap_original_input_directory(self):
        self.target.root = self.fixture.base.fixture.folder
        with self.assertRaises(service.ReviewBlocked):
            self.call()
        self.assertFalse(self.fixture.base.expected_dir.exists())

    def test_target_reconfiguration_cannot_redirect_writes(self):
        other = self.root.with_name("unapproved-restore")
        other.mkdir()
        writer = storage._write_exclusive

        def redirect(path, raw):
            writer(path, raw)
            self.target.root = other

        with patch.object(storage, "_write_exclusive", side_effect=redirect):
            with self.assertRaises(service.ReviewBlocked):
                self.call()
        self.assertFalse(any(other.iterdir()))

    def test_restore_container_replacement_during_source_copy_blocks(self):
        preserved = self.root.with_name("preserved-restore-container")
        writer = storage._write_exclusive

        def replace_container(path, raw):
            writer(path, raw)
            if not preserved.exists():
                self.root.rename(preserved)
                self.root.mkdir()

        with patch.object(storage, "_write_exclusive", side_effect=replace_container):
            with self.assertRaises(service.ReviewBlocked):
                self.call()
        self.assertTrue(preserved.exists())
        self.assertFalse(self.folder.exists())


if __name__ == "__main__":
    unittest.main()
