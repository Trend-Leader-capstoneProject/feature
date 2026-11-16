"""Offline Evidence storage tests; never request database fixtures."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest

from scripts import migration_evidence as evidence


def report():
    return {
        "schema_version": 1,
        "evidence_id": "c66363da-35db-41ac-9748-20c0a2e76bca",
        "observed_at_utc": "2026-11-14T01:02:03Z",
        "inspection_status": "OBSERVED",
        "schema_state": "VERSIONED_OBSERVED",
        "configured_target": {
            "host": "db",
            "port": 3306,
            "database": "trend",
            "user": "migrator",
        },
        "observed_target": {
            "database": "trend",
            "current_user": "migrator@%",
            "server_version": "12.3.2-MariaDB",
            "database_charset": "utf8mb4",
            "database_collation": "utf8mb4_unicode_ci",
        },
        "current_revisions": ["a4d7c9e21f3b"],
        "reason_codes": [],
        "checks": {"read_only": True},
        "image_identity_verification_status": "NOT_VERIFIED",
    }


def test_writes_json_v1_without_changing_observation(tmp_path):
    payload = report()
    result = evidence.write_evidence(tmp_path, payload)
    assert result.success
    assert result.reason_codes == ()
    assert result.report_path == tmp_path / payload["evidence_id"] / "report.json"
    assert json.loads(result.report_path.read_text(encoding="utf-8")) == payload
    assert list(result.report_path.parent.iterdir()) == [result.report_path]
    assert payload == report()


def test_duplicate_keeps_existing_report(tmp_path):
    first = evidence.write_evidence(tmp_path, report())
    original = first.report_path.read_bytes()
    second = evidence.write_evidence(tmp_path, report())
    assert not second.success
    assert second.report_path is None
    assert second.reason_codes == ("EVIDENCE_WRITE_FAILED",)
    assert first.report_path.read_bytes() == original


def test_concurrent_same_id_has_one_winner(tmp_path):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: evidence.write_evidence(tmp_path, report()), range(2))
        )
    assert sum(result.success for result in results) == 1
    path = tmp_path / report()["evidence_id"] / "report.json"
    assert json.loads(path.read_text(encoding="utf-8")) == report()


@pytest.mark.parametrize("kind", ["relative", "missing", "file"])
def test_bad_root_is_not_created(tmp_path, kind):
    root = {
        "relative": Path("relative"),
        "missing": tmp_path / "missing",
        "file": tmp_path / "file",
    }[kind]
    if kind == "file":
        root.write_text("existing", encoding="utf-8")
    assert not evidence.write_evidence(root, report()).success
    assert not (root / report()["evidence_id"]).exists()


@pytest.mark.parametrize(
    "stage", ["write", "flush", "fsync", "publish", "dirsync", "unlink"]
)
def test_io_failure_is_closed_and_never_reuses_id(
    tmp_path, monkeypatch, capsys, caplog, stage
):
    failure = Mock(side_effect=OSError("test-secret-marker mysql://user:password@host"))
    if stage in ("write", "flush"):
        original = evidence.os.fdopen

        class FailingFile:
            def __init__(self, *args, **kwargs):
                self.file = original(*args, **kwargs)

            def __enter__(self):
                self.file.__enter__()
                return self

            def __exit__(self, *args):
                return self.file.__exit__(*args)

            def write(self, value):
                if stage == "write":
                    self.file.write(value[:15])
                    self.file.flush()
                    failure()
                return self.file.write(value)

            def flush(self):
                failure()

            def fileno(self):
                return self.file.fileno()

        monkeypatch.setattr(evidence.os, "fdopen", FailingFile)
    else:
        owner, name = {
            "fsync": (evidence.os, "fsync"),
            "publish": (evidence.os, "link"),
            "dirsync": (evidence, "_sync_directory"),
            "unlink": (evidence.os, "unlink"),
        }[stage]
        monkeypatch.setattr(owner, name, failure)
        if stage == "fsync":
            # Exercise the file fsync, not the earlier root-directory fsync.
            monkeypatch.setattr(evidence, "_sync_directory", lambda path: False)
    result = evidence.write_evidence(tmp_path, report())
    assert not result.success
    assert result.report_path is None
    assert result.reason_codes == ("EVIDENCE_WRITE_FAILED",)
    directory = tmp_path / report()["evidence_id"]
    assert directory.is_dir()
    if stage in {"write", "flush", "fsync", "publish", "dirsync"}:
        assert not (directory / "report.json").exists()
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    assert not evidence.write_evidence(tmp_path, report()).success
    assert before == {p.name: p.read_bytes() for p in directory.iterdir()}
    assert "test-secret-marker" not in repr(result) + caplog.text + str(
        capsys.readouterr()
    )


def test_preempted_final_path_is_not_overwritten(tmp_path, monkeypatch):
    link = evidence.os.link

    def preempt(source, destination):
        Path(destination).write_bytes(b"existing report")
        link(source, destination)

    monkeypatch.setattr(evidence.os, "link", preempt)
    assert not evidence.write_evidence(tmp_path, report()).success
    directory = tmp_path / report()["evidence_id"]
    assert (directory / "report.json").read_bytes() == b"existing report"
    assert (directory / "report.tmp").exists()


@pytest.mark.parametrize("stage", ["during_write", "before_publish"])
def test_process_exit_leaves_incomplete_record(tmp_path, stage):
    # os._exit bypasses Python cleanup, unlike a mocked ordinary exception.
    payload = report()
    program = """
import json, os, sys
from scripts import migration_evidence as evidence
payload = json.loads(sys.argv[2])
if sys.argv[3] == "during_write":
    def interrupted_dump(value, stream, **kwargs):
        stream.write('{"schema_version":')
        stream.flush()
        os._exit(73)
    evidence.json.dump = interrupted_dump
else:
    evidence.os.link = lambda *args, **kwargs: os._exit(73)
evidence.write_evidence(sys.argv[1], payload)
"""
    process = subprocess.run(
        [sys.executable, "-c", program, str(tmp_path), json.dumps(payload), stage],
        capture_output=True,
        timeout=20,
    )
    assert process.returncode == 73, process.stderr
    directory = tmp_path / payload["evidence_id"]
    assert not (directory / "report.json").exists()
    partial = (directory / "report.tmp").read_bytes()
    assert partial
    assert not evidence.write_evidence(tmp_path, payload).success
    assert (directory / "report.tmp").read_bytes() == partial


def test_cli_output_failure_does_not_undo_persistence(tmp_path):
    stored = evidence.write_evidence(tmp_path, report())
    assert stored.success
    original = stored.report_path.read_bytes()
    output = Mock(side_effect=BrokenPipeError("output closed"))
    with pytest.raises(BrokenPipeError):
        output(stored)
    assert stored.success
    assert stored.report_path.read_bytes() == original
    assert not evidence.write_evidence(tmp_path, report()).success


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.pop("checks"),
        lambda p: p.update(schema_version=True),
        lambda p: p.update(evidence_id="../escape"),
        lambda p: p.update(observed_at_utc="2026-11-14T01:02:03"),
        lambda p: p.update(inspection_status="APPROVED"),
        lambda p: p.update(schema_state="EMPTY"),
        lambda p: p.update(reason_codes=["raw exception test-secret-marker"]),
        lambda p: p.update(checks={"exception": "test-secret-marker"}),
        lambda p: p.update(password="test-secret-marker"),
        lambda p: p["configured_target"].update(password="test-secret-marker"),
        lambda p: p["configured_target"].update(host="mysql://user:password@host"),
        lambda p: p["configured_target"].update(
            user="eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signature"
        ),
        lambda p: p["configured_target"].update(port=True),
        lambda p: p.update(current_revisions="a4d7c9e21f3b"),
    ],
)
def test_invalid_or_sensitive_payload_is_rejected_before_reservation(
    tmp_path, mutation, caplog, capsys
):
    payload = report()
    mutation(payload)
    result = evidence.write_evidence(tmp_path, payload)
    assert not result.success
    assert list(tmp_path.iterdir()) == []
    assert "test-secret-marker" not in repr(result) + caplog.text + str(
        capsys.readouterr()
    )


@pytest.mark.parametrize(
    "state",
    ["VERSIONED_OBSERVED", "UNVERSIONED_EMPTY_CANDIDATE", "INDETERMINATE", None],
)
def test_preserves_states_and_unobserved_nulls(tmp_path, state):
    payload = report()
    payload["schema_state"] = state
    if state == "INDETERMINATE":
        payload.update(
            inspection_status="INDETERMINATE",
            reason_codes=["SCHEMA_INDETERMINATE"],
            current_revisions=[None],
        )
    elif state is None:
        payload.update(inspection_status="ERROR", reason_codes=["DB_CONNECTION_FAILED"])
        payload["observed_target"] = dict.fromkeys(payload["observed_target"])
    elif state == "UNVERSIONED_EMPTY_CANDIDATE":
        payload["current_revisions"] = []
    result = evidence.write_evidence(tmp_path, payload)
    assert result.success
    assert json.loads(result.report_path.read_text(encoding="utf-8")) == payload


def test_generated_ids_are_unique_and_path_safe():
    ids = {evidence.new_evidence_id() for _ in range(100)}
    assert len(ids) == 100
    assert all(str(UUID(value)) == value for value in ids)


def test_directory_sync_capability_is_explicit(tmp_path):
    result = evidence.write_evidence(tmp_path, report())
    assert result.success
    assert result.directory_synced == (os.name == "posix")


@pytest.mark.parametrize("failure_call", [2, 3])
def test_directory_sync_failure_after_publish_is_not_completion(
    tmp_path,
    monkeypatch,
    failure_call,
):
    calls = []

    def sync(path):
        calls.append(path)
        if len(calls) == failure_call:
            raise OSError("test-secret-marker")
        return True

    monkeypatch.setattr(evidence, "_sync_directory", sync)
    result = evidence.write_evidence(tmp_path, report())
    assert not result.success
    assert result.report_path is None
    directory = tmp_path / report()["evidence_id"]
    assert (directory / "report.json").exists()
    assert (directory / "report.tmp").exists() == (failure_call == 2)
    assert not evidence.write_evidence(tmp_path, report()).success


def test_validated_payload_is_snapshotted_before_io(tmp_path, monkeypatch):
    payload = report()
    mkdir = Path.mkdir

    def mutate_after_validation(path, *args, **kwargs):
        payload["configured_target"]["host"] = "mysql://user:password@host"
        return mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", mutate_after_validation)
    result = evidence.write_evidence(tmp_path, payload)
    assert result.success
    saved = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert saved == report()


def test_pre_db_root_check_never_creates_root(tmp_path):
    assert evidence.evidence_root_available(tmp_path)
    assert not evidence.evidence_root_available(tmp_path / "missing")
    assert list(tmp_path.iterdir()) == []


def test_preempted_temporary_file_is_preserved(tmp_path, monkeypatch):
    mkdir = Path.mkdir

    def preempt(path, *args, **kwargs):
        mkdir(path, *args, **kwargs)
        (path / "report.tmp").write_bytes(b"existing partial record")

    monkeypatch.setattr(Path, "mkdir", preempt)
    assert not evidence.write_evidence(tmp_path, report()).success
    directory = tmp_path / report()["evidence_id"]
    assert (directory / "report.tmp").read_bytes() == b"existing partial record"
    assert not (directory / "report.json").exists()


def test_unwritable_root_is_rejected_without_reservation(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence.os, "access", lambda *args: False)
    assert not evidence.evidence_root_available(tmp_path)
    assert not evidence.write_evidence(tmp_path, report()).success
    assert list(tmp_path.iterdir()) == []


def test_unicode_is_written_as_utf8(tmp_path):
    payload = report()
    payload["configured_target"]["database"] = "트렌드"
    result = evidence.write_evidence(tmp_path, payload)
    assert result.success
    assert "트렌드".encode("utf-8") in result.report_path.read_bytes()


@pytest.mark.parametrize("fail", [False, True])
def test_posix_directory_sync_branch_closes_descriptor(tmp_path, monkeypatch, fail):
    """Mocked syscall contract; this is not Linux filesystem validation."""
    from types import SimpleNamespace

    system = SimpleNamespace(
        name="posix",
        O_RDONLY=0,
        O_DIRECTORY=1,
        O_NOFOLLOW=2,
        open=Mock(return_value=17),
        close=Mock(),
        fsync=Mock(side_effect=OSError("test-secret-marker") if fail else None),
    )
    monkeypatch.setattr(evidence, "os", system)
    if fail:
        with pytest.raises(OSError):
            evidence._sync_directory(tmp_path)
    else:
        assert evidence._sync_directory(tmp_path)
    system.open.assert_called_once_with(tmp_path, 3)
    system.fsync.assert_called_once_with(17)
    system.close.assert_called_once_with(17)


def test_reparse_root_is_rejected_without_writes(tmp_path, monkeypatch):
    from types import SimpleNamespace

    lstat = Path.lstat

    def reparse(path, *args, **kwargs):
        if path == tmp_path:
            return SimpleNamespace(st_mode=0o40700, st_file_attributes=0x400)
        return lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", reparse)
    assert not evidence.evidence_root_available(tmp_path)
    assert not evidence.write_evidence(tmp_path, report()).success
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(
    os.name != "posix",
    reason="POSIX mode/owner checks; Windows requires ACL verification",
)
def test_posix_private_permissions_and_insecure_root_rejection(tmp_path):
    tmp_path.chmod(0o700)
    result = evidence.write_evidence(tmp_path, report())
    assert result.success
    assert result.report_path.stat().st_mode & 0o777 == 0o600
    assert result.report_path.parent.stat().st_mode & 0o777 == 0o700
    tmp_path.chmod(0o755)
    assert not evidence.write_evidence(tmp_path, report()).success
