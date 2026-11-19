"""B41-01..08: synthetic A1/4A inputs, no operational evidence or HTTP."""

import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

import fr_b02b_a1_adapter as a1
import fr_b02b_observation as observation
from fr_b02b_cli import run_cli
from test_fr_b02b_a1_adapter import example


class ReviewCandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive = self.root / "synthetic A1.zip"
        approvals, batch = example()
        with ZipFile(self.archive, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr(a1.A1_ZIP_APPROVALS, json.dumps(approvals))
            archive.writestr(a1.A1_ZIP_BATCH, json.dumps(batch))
        snapshot = a1.load_a1_snapshot(self.archive)
        when = datetime(2026, 11, 10, 8, tzinfo=timezone.utc)
        with patch.object(observation, "utc_now", return_value=when):
            saved = observation.record_observation(
                snapshot, self.archive, self.root / "local observations", when
            )
        self.folder = Path(saved["directory"])
        self.record_path = self.folder / "observation.json"
        self.index_path = self.folder / "index.json"
        self.record_raw = self.record_path.read_bytes()
        self.index_raw = self.index_path.read_bytes()
        self.record = json.loads(self.record_raw)

    def invoke(self, archive=None, folder=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr), \
                patch("builtins.input", side_effect=AssertionError("no prompt")), \
                patch("webbrowser.open", side_effect=AssertionError("no browser")), \
                patch("socket.create_connection", side_effect=AssertionError("no HTTP")):
            try:
                code = run_cli([
                    "review-candidate", "--zip", str(archive or self.archive),
                    "--record-dir", str(folder or self.folder),
                ], input_func=lambda _: self.fail("no confirmation allowed"))
            except SystemExit as exc:
                code = exc.code
        return code, stdout.getvalue(), stderr.getvalue()

    def assert_blocked(self, result):
        self.assertEqual(result[0], 1, result)
        self.assertEqual(result[1], "", result)
        self.assertTrue(result[2].startswith("BLOCKED: "), result)
        self.assertEqual(len(result[2].splitlines()), 1)

    def rewrite_record(self, **changes):
        record = {**self.record, **changes}
        raw = observation.canonical_bytes(record)
        self.record_path.write_bytes(raw)
        index = json.loads(self.index_raw)
        index["artifact_sha256"] = "sha256:" + hashlib.sha256(raw).hexdigest()
        self.index_path.write_bytes(observation.canonical_bytes(index))

    def tree_snapshot(self):
        return {
            str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in self.root.rglob("*") if p.is_file()
        }

    def test_b41_01_exact_candidate_fields_from_validated_inputs(self):
        code, stdout, stderr = self.invoke()
        self.assertEqual(code, 0, stderr)
        self.assertEqual(stderr, "")
        self.assertEqual(len(stdout.splitlines()), 1)
        self.assertEqual(json.loads(stdout), {
            "status": "REVIEW_CANDIDATE_HOLD",
            "local_evidence_id": self.record["evidence_id"],
            **{key: self.record[key] for key in (
                "trend_ref", "content_ref", "review_evidence_id", "source_url",
                "confirmed_at_utc", "record_created_at_utc",
                "review_result", "publish_authorization",
            )},
        })

    def test_b41_02_each_binding_mismatch_blocks_even_with_matching_hash(self):
        for key, value in (
            ("trend_ref", "different"), ("content_ref", "sha256:" + "0" * 64),
            ("review_evidence_id", "different"),
            ("source_url", self.record["source_url"] + "/"),
        ):
            with self.subTest(key=key):
                self.rewrite_record(**{key: value})
                self.assert_blocked(self.invoke())

    def test_b41_01_candidate_uses_validated_json_not_a_later_file_version(self):
        original_validator = observation._validate_records

        def replace_after_validation(*args):
            record = original_validator(*args)
            self.rewrite_record(confirmed_at_utc="2026-11-10T09:00:00Z",
                                record_created_at_utc="2026-11-10T09:00:01Z")
            return record

        with patch.object(observation, "_validate_records", side_effect=replace_after_validation):
            code, stdout, stderr = self.invoke()
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout)["confirmed_at_utc"], self.record["confirmed_at_utc"])
        self.assertEqual(json.loads(stdout)["record_created_at_utc"],
                         self.record["record_created_at_utc"])
        self.assertNotEqual(self.record_path.read_bytes(), self.record_raw)

    def test_b41_01_phase4a_public_result_is_unchanged(self):
        self.assertEqual(observation.verify_observation(self.archive, self.folder), {
            "status": "PASS_LOCAL_INTEGRITY_ONLY", "evidence_id": self.folder.name,
            "publish_authorization": "NONE",
        })

    def test_b41_03_missing_corrupt_and_hash_mismatched_files_are_not_repaired(self):
        for path, original in ((self.record_path, self.record_raw),
                               (self.index_path, self.index_raw)):
            for raw in (None, b"invalid JSON", original + b" "):
                with self.subTest(file=path.name, raw=raw):
                    if raw is None:
                        path.unlink()
                    else:
                        path.write_bytes(raw)
                    before = self.tree_snapshot()
                    self.assert_blocked(self.invoke())
                    self.assertEqual(self.tree_snapshot(), before)
                    path.write_bytes(original)
        index = json.loads(self.index_raw)
        index["artifact_sha256"] = "sha256:" + "0" * 64
        self.index_path.write_bytes(observation.canonical_bytes(index))
        before = self.tree_snapshot()
        self.assert_blocked(self.invoke())
        self.assertEqual(self.tree_snapshot(), before)

    def test_b41_03_unsafe_states_block_even_when_rehashed(self):
        for key, value in (
            ("review_result", "ACCEPTED"), ("publish_authorization", "APPROVED"),
            ("actor_assurance", "VERIFIED"), ("clock_source", "INDEPENDENT"),
        ):
            with self.subTest(key=key):
                self.rewrite_record(**{key: value})
                self.assert_blocked(self.invoke())
        self.record_path.write_bytes(self.record_raw)
        index = json.loads(self.index_raw)
        index["status"] = "ACCEPTED"
        self.index_path.write_bytes(observation.canonical_bytes(index))
        self.assert_blocked(self.invoke())

    def test_b41_03_id_zip_digest_and_invalid_local_times_block(self):
        for key, value in (
            ("evidence_id", "LOCAL-OBS-00000000000040008000000000000000"),
            ("a1_archive_sha256", "sha256:" + "0" * 64),
            ("confirmed_at_utc", "not-a-time"),
            ("record_created_at_utc", "2026-11-09T08:00:00Z"),
        ):
            with self.subTest(key=key):
                self.rewrite_record(**{key: value})
                self.assert_blocked(self.invoke())

    def test_b41_04_invalid_or_changed_zip_blocks_without_modification(self):
        original = self.archive.read_bytes()
        for raw in (b"invalid ZIP", original + b"changed"):
            with self.subTest(raw_length=len(raw)):
                self.archive.write_bytes(raw)
                before = self.tree_snapshot()
                self.assert_blocked(self.invoke())
                self.assertEqual(self.tree_snapshot(), before)

    def test_b41_04_zip_change_during_verification_blocks(self):
        original_reader = observation._read_record_file
        records_before = (self.record_path.read_bytes(), self.index_path.read_bytes())

        def change_zip(path):
            raw = original_reader(path)
            if path.name == "index.json":
                self.archive.write_bytes(self.archive.read_bytes() + b"changed externally")
            return raw

        with patch.object(observation, "_read_record_file", side_effect=change_zip):
            self.assert_blocked(self.invoke())
        self.assertEqual(self.archive.read_bytes()[-18:], b"changed externally")
        self.assertEqual((self.record_path.read_bytes(), self.index_path.read_bytes()),
                         records_before)

    def test_b41_05_repeated_reads_preserve_ids_and_exact_recorded_times(self):
        # Z/+00:00 and fractions are passed through, never reformatted or sampled.
        self.rewrite_record(confirmed_at_utc="2026-11-10T08:00:00.123+00:00",
                            record_created_at_utc="2026-11-10T08:00:01.456Z")
        with patch.object(observation, "utc_now", side_effect=AssertionError("no clock")), \
                patch("uuid.uuid4", side_effect=AssertionError("no new evidence ID")):
            first, second = self.invoke(), self.invoke()
        self.assertEqual(first[0], 0, first)
        self.assertEqual(first, second)
        result = json.loads(first[1])
        self.assertEqual(result["confirmed_at_utc"], "2026-11-10T08:00:00.123+00:00")
        self.assertEqual(result["record_created_at_utc"], "2026-11-10T08:00:01.456Z")
        self.assertEqual(result["local_evidence_id"], self.folder.name)

    def test_b41_06_candidate_does_not_promote_local_assurance_or_hold(self):
        result = self.invoke()
        self.assertEqual(result[0], 0, result)
        candidate = json.loads(result[1])
        self.assertEqual(candidate["review_result"], "HOLD")
        self.assertEqual(candidate["publish_authorization"], "NONE")
        for key in ("observed_at", "collected_at", "reviewer_ref", "reviewed_at",
                    "observation_evidence_ref", "approved_by", "g5_status", "g6_status"):
            self.assertNotIn(key, candidate)
        self.assertEqual(json.loads(self.record_path.read_bytes())["actor_assurance"],
                         "UNVERIFIED")
        self.assertEqual(json.loads(self.record_path.read_bytes())["clock_source"],
                         "LOCAL_SYSTEM_CLOCK")

    def test_b41_07_success_and_failure_are_read_only(self):
        original_open = Path.open

        def read_only_open(path, mode="r", *args, **kwargs):
            self.assertFalse(any(flag in mode for flag in "wax+"), "file write attempted")
            return original_open(path, mode, *args, **kwargs)

        for valid in (True, False):
            with self.subTest(valid=valid):
                if not valid:
                    self.record_path.write_bytes(b"corrupted")
                before = self.tree_snapshot()
                with patch.object(Path, "open", new=read_only_open), \
                        patch.object(Path, "mkdir", side_effect=AssertionError("no mkdir")), \
                        patch.object(observation, "record_observation",
                                     side_effect=AssertionError("no record creation")):
                    result = self.invoke()
                if valid:
                    self.assertEqual(result[0], 0, result)
                else:
                    self.assert_blocked(result)
                self.assertEqual(self.tree_snapshot(), before)

    def test_b41_08_errors_are_concise_and_do_not_echo_paths_or_input(self):
        self.assert_blocked(result := self.invoke(
            archive=self.root / "private-person-secret.zip"))
        self.assertNotIn(str(self.root), result[2])
        self.assertNotIn("private-person-secret", result[2])
        with ZipFile(self.archive, "w") as archive:
            archive.writestr(a1.A1_ZIP_APPROVALS,
                             b'{"private-secret":0,"private-secret":1}')
            archive.writestr(a1.A1_ZIP_BATCH, b"{}")
        self.assert_blocked(result := self.invoke())
        self.assertNotIn("private-secret", result[2])

    def test_b41_07_08_cli_process_is_noninteractive_read_only_and_no_network(self):
        cli = Path(__file__).resolve().parents[1] / "fr_b02b_cli.py"
        # Audit the actual entrypoint, including imports. Reads and stdout/stderr
        # are allowed; filesystem mutation, network and DB connections are not.
        script = """
import os, runpy, sys
def forbid_side_effects(event, args):
    if event == 'open':
        mode, flags = args[1], args[2]
        if (mode and any(c in mode for c in 'wax+')) or (
            flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        ):
            raise AssertionError('file write forbidden')
    if event in ('os.mkdir', 'os.remove', 'os.rename', 'os.rmdir', 'os.truncate',
                 'os.chmod', 'os.utime', 'socket.connect', 'socket.getaddrinfo',
                 'sqlite3.connect', 'subprocess.Popen', 'os.system', 'webbrowser.open'):
        raise AssertionError('side effect forbidden: ' + event)
sys.addaudithook(forbid_side_effects)
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name='__main__')
"""
        for valid in (True, False):
            with self.subTest(valid=valid):
                if not valid:
                    self.index_path.unlink()
                before = self.tree_snapshot()
                process = subprocess.run(
                    [sys.executable, "-B", "-c", script, str(cli), "review-candidate",
                     "--zip", str(self.archive), "--record-dir", str(self.folder)],
                    cwd=cli.parent, input="", capture_output=True, text=True, timeout=10,
                )
                result = (process.returncode, process.stdout, process.stderr)
                if valid:
                    self.assertEqual(result[0], 0, result)
                    self.assertEqual(json.loads(result[1])["status"], "REVIEW_CANDIDATE_HOLD")
                    self.assertEqual(result[2], "")
                else:
                    self.assert_blocked(result)
                self.assertEqual(self.tree_snapshot(), before)


if __name__ == "__main__":
    unittest.main()
