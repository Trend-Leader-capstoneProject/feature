"""Real filesystem exclusion tests; mocked sync is NOT durability evidence."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256

import pytest

from scripts import migration_apply_audit as audit

PIN = "a" * 64


@pytest.fixture
def store(tmp_path, monkeypatch):
    root = tmp_path / "audit"
    root.mkdir(mode=0o700)
    # Windows cannot fsync directories. Emulate that primitive for orchestration
    # tests only; a separate test proves the actual Windows store rejects APPLY.
    monkeypatch.setattr(audit, "_sync_directory", lambda path: True)
    return audit.FileApplyAudit(root)


def consume(store, identifier="approval-001"):
    return store.consume(identifier, manifest_sha256=PIN, evidence_sha256=PIN)


def test_new_instance_cannot_reuse_persisted_id(store):
    claim = consume(store)
    record = json.loads((claim.directory / "started.json").read_text())
    assert record["manifest_sha256"] == PIN
    with pytest.raises(audit.AuditRejected, match="^APPROVAL_ALREADY_USED$"):
        consume(audit.FileApplyAudit(store.root))


def test_atomic_concurrent_consumption_allows_one(store):
    def attempt(_):
        try:
            consume(store)
            return "CLAIMED"
        except audit.AuditRejected as error:
            return error.args[0]

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(attempt, range(16)))
    assert outcomes.count("CLAIMED") == 1
    assert outcomes.count("APPROVAL_ALREADY_USED") == 15


def test_partial_crash_claim_stays_consumed(store):
    (store.root / sha256(b"approval-001").hexdigest()).mkdir(mode=0o700)
    with pytest.raises(audit.AuditRejected, match="^APPROVAL_ALREADY_USED$"):
        consume(store)


def test_failure_after_reservation_burns_id(store, monkeypatch):
    monkeypatch.setattr(audit, "_publish", lambda *a: (_ for _ in ()).throw(OSError()))
    with pytest.raises(audit.AuditRejected, match="^AUDIT_WRITE_FAILED$"):
        consume(store)
    with pytest.raises(audit.AuditRejected, match="^APPROVAL_ALREADY_USED$"):
        consume(store)


def test_failed_sync_before_reservation_denies_without_claim(store, monkeypatch):
    monkeypatch.setattr(audit, "_sync_directory", lambda path: False)
    with pytest.raises(audit.AuditRejected, match="^AUDIT_WRITE_FAILED$"):
        consume(store)
    assert list(store.root.iterdir()) == []


@pytest.mark.parametrize("where", ["root_after_mkdir", "file", "record_directory"])
def test_each_required_sync_failure_denies_and_burns_claim(store, monkeypatch, where):
    if where == "file":
        def fail_sync(fd):
            raise OSError

        monkeypatch.setattr(audit.os, "fsync", fail_sync)
    else:
        count = 0

        def sync(path):
            nonlocal count
            count += 1
            return count != (2 if where == "root_after_mkdir" else 3)

        monkeypatch.setattr(audit, "_sync_directory", sync)
    with pytest.raises(audit.AuditRejected, match="^AUDIT_WRITE_FAILED$"):
        consume(store)
    assert len(list(store.root.iterdir())) == 1


def test_completion_is_exclusive_fixed_codes_and_preserves_started(store):
    claim = consume(store)
    started = (claim.directory / "started.json").read_bytes()
    store.finish(claim, "UNKNOWN", "APPLY_OUTCOME_UNKNOWN")
    original = (claim.directory / "result.json").read_bytes()
    with pytest.raises(audit.AuditRejected, match="^AUDIT_WRITE_FAILED$"):
        store.finish(claim, "APPLIED", "APPLIED")
    assert (claim.directory / "started.json").read_bytes() == started
    assert (claim.directory / "result.json").read_bytes() == original


def test_no_path_injection_or_raw_identifier_in_record(store):
    marker = "../../outside-sensitive-marker"
    claim = consume(store, marker)
    assert claim.directory.parent == store.root
    assert marker.encode() not in (claim.directory / "started.json").read_bytes()


def test_raw_error_or_secret_cannot_be_recorded(store):
    claim = consume(store)
    with pytest.raises(audit.AuditRejected, match="^AUDIT_WRITE_FAILED$"):
        store.finish(claim, "UNKNOWN", "mysql://user:password@host")
    assert not (claim.directory / "result.json").exists()


@pytest.mark.parametrize(("status", "reason"), [
    ("APPLIED", "LIVE_CHECK_FAILED"), ("FAILED", "APPLIED"),
    ("UNKNOWN", "APPLIED"),
])
def test_contradictory_completion_is_rejected(store, status, reason):
    claim = consume(store)
    with pytest.raises(audit.AuditRejected, match="^AUDIT_WRITE_FAILED$"):
        store.finish(claim, status, reason)
    assert not (claim.directory / "result.json").exists()


def test_missing_root_is_not_created(tmp_path):
    root = tmp_path / "missing"
    with pytest.raises(audit.AuditRejected, match="^AUDIT_WRITE_FAILED$"):
        consume(audit.FileApplyAudit(root))
    assert not root.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows directory sync unsupported")
def test_windows_real_storage_denies_before_claim(tmp_path):
    root = tmp_path / "audit"
    root.mkdir()
    with pytest.raises(audit.AuditRejected, match="^AUDIT_WRITE_FAILED$"):
        consume(audit.FileApplyAudit(root))
    assert list(root.iterdir()) == []


@pytest.mark.skipif(os.name != "posix", reason="requires actual POSIX fsync")
def test_posix_file_and_directory_sync(tmp_path):
    root = tmp_path / "audit"
    root.mkdir(mode=0o700)
    store = audit.FileApplyAudit(root)
    claim = consume(store)
    store.finish(claim, "APPLIED", "APPLIED")
    assert (claim.directory / "result.json").is_file()
