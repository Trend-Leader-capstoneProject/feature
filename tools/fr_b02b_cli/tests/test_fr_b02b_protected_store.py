"""B42-03/05: synthetic byte sets, real temporary writes, no valid registration."""

import json
import os
import subprocess
import unittest
from contextlib import nullcontext
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import fr_b02b_a1_adapter as a1
import fr_b02b_observation as observation
import fr_b02b_protected_store as storage
import fr_b02b_review_service as service
import fr_b02b_reviewer_allowlist as allowlist
import fr_b02b_windows_auth as windows_auth
import test_fr_b02b_review_decision as decisions


class ProtectedStoreTests(unittest.TestCase):
    def setUp(self):
        self.fixture = decisions.ReviewDecisionTests("test_auth_failure_prevents_review_callback")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        with patch.object(observation, "utc_now", return_value=self.fixture.reviewed_at):
            self.pending = self.fixture.collect(Mock(return_value=("ACCEPTED", "")))
        self.root = self.fixture.root / "staging-area"
        self.root.mkdir()
        self.store = storage.ProtectedEvidenceStore(self.root, Mock(return_value=True))
        self.expected_dir = self.root / (".review-staging-" + self.fixture.folder.name)

    def originals(self):
        return {p: p.read_bytes() for p in (
            self.fixture.archive, self.fixture.folder / "observation.json",
            self.fixture.folder / "index.json",
        )}

    def metadata(self):
        return observation.canonical_bytes({
            "local_evidence_id": self.pending.local_evidence_id,
            "reviewer_sid": self.pending.reviewer_sid,
            "review_result": self.pending.review_result,
            "decision_reason": self.pending.decision_reason,
            "reviewed_at_utc": self.pending.reviewed_at_utc,
            "publish_authorization": "NONE",
            "a1_archive_sha256": observation.digest(self.pending.evidence.a1_snapshot.archive_bytes),
            "observation_sha256": observation.digest(self.pending.evidence.record_bytes),
            "index_sha256": observation.digest(self.pending.evidence.index_bytes),
        })

    def stage(self, decision=None, store=None, source=None, sid=decisions.SID):
        with patch.object(windows_auth, "get_current_process_sid", return_value=sid), \
                patch.object(observation, "utc_now",
                             return_value=self.fixture.reviewed_at + timedelta(seconds=1)):
            return service.stage_pending_review(
                decision if decision is not None else self.pending,
                self.fixture.archive, self.fixture.folder,
                store=store if store is not None else self.store,
                allowlist_source=source if source is not None else self.fixture.source,
            )

    def test_validated_bytes_stage_as_hold_without_registration_or_original_mutation(self):
        before = self.originals()
        result = self.stage()
        self.assertIsNotNone(result, "validated bytes must reach HOLD staging")
        self.assertEqual(result.state, "HOLD")
        self.assertEqual(result.publish_authorization, "NONE")
        self.assertFalse(hasattr(result, "registration_id"))
        self.assertEqual(result.staging_dir, self.expected_dir)
        self.assertEqual({p.name for p in result.staging_dir.iterdir()}, {
            "a1_archive.zip", "observation.json", "index.json", "pending_review.json",
        })
        for name, raw in (
            ("a1_archive.zip", self.pending.evidence.a1_snapshot.archive_bytes),
            ("observation.json", self.pending.evidence.record_bytes),
            ("index.json", self.pending.evidence.index_bytes),
            ("pending_review.json", self.metadata()),
        ):
            self.assertEqual((result.staging_dir / name).read_bytes(), raw)
        self.assertEqual(self.originals(), before)

    def test_each_changed_source_is_rejected_before_store_call(self):
        originals = self.originals()
        for path, raw in originals.items():
            with self.subTest(file=path.name):
                path.write_bytes(raw + b"changed")
                before = self.originals()
                spy = Mock(spec=storage.ProtectedEvidenceStore)
                with self.assertRaises(service.ReviewBlocked):
                    self.stage(store=spy)
                spy.stage.assert_not_called()
                self.assertEqual(self.originals(), before)  # No automatic repair.
                self.assertEqual(list(self.root.iterdir()), [])
                path.write_bytes(raw)

    def test_coherently_rehashed_replacement_is_not_the_reviewed_snapshot(self):
        record_path = self.fixture.folder / "observation.json"
        index_path = self.fixture.folder / "index.json"
        record = json.loads(record_path.read_bytes())
        record["confirmed_at_utc"] = "2026-11-10T08:00:01Z"
        record["record_created_at_utc"] = "2026-11-10T08:00:01Z"
        raw = observation.canonical_bytes(record)
        record_path.write_bytes(raw)
        index = json.loads(index_path.read_bytes())
        index["artifact_sha256"] = observation.digest(raw)
        index_path.write_bytes(observation.canonical_bytes(index))
        self.assertEqual(observation.verify_observation(
            self.fixture.archive, self.fixture.folder)["status"], "PASS_LOCAL_INTEGRITY_ONLY")
        spy = Mock(spec=storage.ProtectedEvidenceStore)
        with self.assertRaises(service.ReviewBlocked):
            self.stage(store=spy)
        spy.stage.assert_not_called()

    def test_forged_pending_fields_are_not_staged(self):
        for changes in (
            {"publish_authorization": "APPROVED"}, {"review_result": "REVOKED"},
            {"review_result": "HOLD", "decision_reason": ""},
            {"decision_reason": "가" * 501}, {"local_evidence_id": "invalid"},
            {"reviewed_at_utc": "2026-11-09T08:00:00Z"},
            {"reviewer_sid": "S-1-5-21-100-200-300-1002"},
        ):
            with self.subTest(fields=tuple(changes)):
                spy = Mock(spec=storage.ProtectedEvidenceStore)
                with self.assertRaises(service.ReviewBlocked):
                    self.stage(replace(self.pending, **changes), store=spy)
                spy.stage.assert_not_called()

    def test_permission_loss_before_staging_blocks_store(self):
        source = allowlist.AllowlistSource(self.fixture.source.path, Mock(return_value=False))
        spy = Mock(spec=storage.ProtectedEvidenceStore)
        with self.assertRaises(service.ReviewBlocked):
            self.stage(store=spy, source=source)
        spy.stage.assert_not_called()
        other_sid = "S-1-5-21-100-200-300-1002"
        self.fixture.source.path.write_text(json.dumps({
            "schema": allowlist.SCHEMA, "reviewers": [
                {"sid": sid, "active": True, "role": "EVIDENCE_REVIEWER"}
                for sid in (decisions.SID, other_sid)
            ],
        }), encoding="utf-8")
        with self.assertRaisesRegex(service.ReviewBlocked, "identity changed"):
            self.stage(store=spy, sid=other_sid)
        spy.stage.assert_not_called()

    def test_store_independently_rejects_unverified_or_misbound_bytes(self):
        evidence = self.pending.evidence
        for forged in (
            replace(evidence, a1_snapshot=None),
            replace(evidence, record_bytes=evidence.record_bytes + b" "),
            replace(evidence, index_bytes=b"{}"),
            replace(evidence, a1_snapshot=replace(evidence.a1_snapshot, archive_bytes=b"not ZIP")),
            replace(evidence, a1_snapshot=replace(evidence.a1_snapshot, title="unverified title")),
        ):
            with self.subTest(kind=repr(forged)[:30]):
                with self.assertRaises(storage.StagingError):
                    self.store.stage(forged, self.metadata(), revalidate_input=Mock())
                self.assertEqual(list(self.root.iterdir()), [])
        metadata = json.loads(self.metadata())
        metadata["observation_sha256"] = "sha256:" + "0" * 64
        with self.assertRaises(storage.StagingError):
            self.store.stage(evidence, observation.canonical_bytes(metadata),
                             revalidate_input=Mock())

    def test_archive_type_and_size_are_rejected_before_zip_parsing_or_staging(self):
        invalid_values = (
            ("none", None), ("integer", 1), ("string", "synthetic-private-archive"),
            ("bytearray", bytearray(b"PK")), ("memoryview", memoryview(b"PK")),
            ("oversized", b"x" * (a1.MAX_ARCHIVE_BYTES + 1)),
        )
        for name, raw in invalid_values:
            with self.subTest(case=name):
                evidence = replace(self.pending.evidence, a1_snapshot=replace(
                    self.pending.evidence.a1_snapshot, archive_bytes=raw
                ))
                revalidate = Mock()
                with patch.object(a1, "ZipFile", side_effect=AssertionError("no ZIP parse")) as zipfile:
                    with self.assertRaises(storage.StagingError) as blocked:
                        self.store.stage(evidence, self.metadata(), revalidate_input=revalidate)
                    zipfile.assert_not_called()
                revalidate.assert_not_called()
                self.assertNotIn("synthetic-private-archive", str(blocked.exception))
                self.assertEqual(list(self.root.iterdir()), [])

    def test_existing_directory_and_files_are_never_overwritten(self):
        self.expected_dir.mkdir()
        sentinel = self.expected_dir / "a1_archive.zip"
        sentinel.write_bytes(b"preserve-existing")
        before = self.originals()
        with self.assertRaises(service.ReviewBlocked):
            self.stage()
        self.assertEqual(sentinel.read_bytes(), b"preserve-existing")
        self.assertEqual(self.originals(), before)
        self.assertEqual(list(self.expected_dir.iterdir()), [sentinel])
        race_root = self.root / "file-collision"
        race_root.mkdir()
        race_store = storage.ProtectedEvidenceStore(race_root, Mock(return_value=True))
        real_writer = storage._write_exclusive
        created = []

        def collide(path, raw):
            path.write_bytes(b"preserve-colliding-file")
            created.append(path)
            real_writer(path, raw)

        with patch.object(storage, "_write_exclusive", side_effect=collide):
            with self.assertRaises(service.ReviewBlocked):
                self.stage(store=race_store)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].read_bytes(), b"preserve-colliding-file")
        self.assertEqual(self.originals(), before)

    def test_short_write_return_is_blocked_without_overwriting_or_repair(self):
        real_open = Path.open

        class ShortWriter:
            def __init__(self, file):
                self.file = file

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return self.file.__exit__(*args)

            def write(self, raw):
                return self.file.write(raw[:5])

        def open_short(path, mode="r", *args, **kwargs):
            file = real_open(path, mode, *args, **kwargs)
            return ShortWriter(file) if mode == "xb" else file

        before = self.originals()
        with patch.object(Path, "open", new=open_short):
            with self.assertRaisesRegex(service.ReviewBlocked, "HOLD"):
                self.stage()
        self.assertEqual((self.expected_dir / "a1_archive.zip").stat().st_size, 5)
        self.assertEqual(self.originals(), before)

    def test_write_partial_write_and_fsync_failures_leave_unusable_remnants(self):
        real_writer = storage._write_exclusive
        for mode in ("write", "partial", "fsync"):
            with self.subTest(mode=mode):
                root = self.root / mode
                root.mkdir()
                store = storage.ProtectedEvidenceStore(root, Mock(return_value=True))
                calls = []

                def writer(path, raw):
                    calls.append(path)
                    if mode == "write":
                        raise PermissionError("synthetic-private-path")
                    if mode == "partial" and len(calls) == 2:
                        with path.open("xb") as file:
                            file.write(raw[:5])
                        raise OSError("partial write")
                    real_writer(path, raw)

                before = self.originals()
                fsync_fault = (patch.object(os, "fsync", side_effect=OSError("fsync failure"))
                               if mode == "fsync" else nullcontext())
                with patch.object(storage, "_write_exclusive", side_effect=writer), fsync_fault:
                    with self.assertRaisesRegex(service.ReviewBlocked, "HOLD"):
                        self.stage(store=store)
                remnants = list(root.iterdir())
                self.assertEqual(len(remnants), 1)
                self.assertFalse((remnants[0] / "registration_complete.json").exists())
                self.assertFalse((remnants[0] / "registration.json").exists())
                if mode != "write":
                    self.assertTrue(list(remnants[0].iterdir()))
                self.assertEqual(self.originals(), before)

    def test_input_replacement_during_write_is_blocked_and_not_repaired(self):
        real_writer = storage._write_exclusive
        changed = self.fixture.archive.read_bytes() + b"external replacement"

        def writer(path, raw):
            real_writer(path, raw)
            if path.name == "a1_archive.zip":
                self.fixture.archive.write_bytes(changed)

        with patch.object(storage, "_write_exclusive", side_effect=writer):
            with self.assertRaises(service.ReviewBlocked):
                self.stage()
        self.assertEqual(self.fixture.archive.read_bytes(), changed)
        self.assertTrue(self.expected_dir.exists())
        self.assertFalse((self.expected_dir / "registration_complete.json").exists())

    def test_staged_corruption_extra_files_and_protection_loss_block(self):
        real_writer = storage._write_exclusive
        for mode in ("corrupt", "extra", "protection"):
            with self.subTest(mode=mode):
                root = self.root / mode
                root.mkdir()
                allowed = [True]
                store = storage.ProtectedEvidenceStore(root, lambda _path: allowed[0])

                def writer(path, raw):
                    real_writer(path, raw)
                    if path.name == "pending_review.json":
                        if mode == "corrupt":
                            (path.parent / "index.json").write_bytes(b"corrupt")
                        elif mode == "extra":
                            (path.parent / "unexpected.txt").write_bytes(b"extra")
                        else:
                            allowed[0] = False

                with patch.object(storage, "_write_exclusive", side_effect=writer):
                    with self.assertRaises(service.ReviewBlocked):
                        self.stage(store=store)

    def test_unprotected_ambiguous_and_git_roots_are_blocked(self):
        fake_repo = self.fixture.root / "synthetic-repo"
        fake_repo.mkdir()
        (fake_repo / ".git").mkdir()
        git_root = fake_repo / "output"
        git_root.mkdir()
        not_a_directory = self.root / "file"
        not_a_directory.write_bytes(b"preserve")
        for root, verifier in (
            (self.root, Mock(return_value=False)),
            (self.root, Mock(side_effect=PermissionError("private ACL"))),
            (git_root, Mock(return_value=True)),
            (not_a_directory, Mock(return_value=True)),
            (self.fixture.folder, Mock(return_value=True)),
            (self.fixture.root, Mock(return_value=True)),
            (self.root / ".." / "ambiguous", Mock(return_value=True)),
        ):
            with self.subTest(root=root.name):
                before = self.fixture.files()
                with self.assertRaises(service.ReviewBlocked):
                    self.stage(store=storage.ProtectedEvidenceStore(root, verifier))
                self.assertEqual(self.fixture.files(), before)

    def test_real_symlink_root_is_blocked(self):
        link = self.fixture.root / "staging-symlink"
        try:
            link.symlink_to(self.root, target_is_directory=True)
        except OSError as exc:
            self.skipTest("test symlinks unavailable: " + type(exc).__name__)
        self.addCleanup(link.unlink)
        with self.assertRaises(service.ReviewBlocked):
            self.stage(store=storage.ProtectedEvidenceStore(link, Mock(return_value=True)))
        self.assertEqual(list(self.root.iterdir()), [])

    @unittest.skipUnless(os.name == "nt", "real Windows reparse point required")
    def test_real_windows_junction_root_is_blocked(self):
        link = self.fixture.root / "staging-junction"
        for path in (link, self.root):
            self.assertTrue(path.absolute().is_relative_to(self.fixture.root.absolute()))
            self.assertFalse(any(char in str(path) for char in '%!^"&|<>\r\n'))
        cmd = str(Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe")
        result = subprocess.run([cmd, "/d", "/c", "mklink", "/J", str(link), str(self.root)],
                                capture_output=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 0)

        def cleanup():
            self.assertTrue(link.is_junction())
            link.rmdir()  # Only the owned link, never recursive deletion.

        self.addCleanup(cleanup)
        with self.assertRaises(service.ReviewBlocked):
            self.stage(store=storage.ProtectedEvidenceStore(link, Mock(return_value=True)))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_no_configured_store_remains_blocked(self):
        before = self.fixture.files()
        with self.assertRaisesRegex(service.ReviewBlocked, "not configured"):
            service.stage_pending_review(self.pending, self.fixture.archive, self.fixture.folder)
        self.assertEqual(self.fixture.files(), before)


if __name__ == "__main__":
    unittest.main()
