"""Pre-APPLY, single-use filesystem journal candidate, separate from Evidence.

Only POSIX directory-fsync capable storage is supported. Provisioning, protected
ancestors, mount durability and access controls require independent verification.
No operational path/default is selected here. Never remove incomplete claims.
"""

import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from scripts.migration_evidence import _sync_directory, _validated_root

OUTCOMES = frozenset({"APPLIED", "FAILED", "UNKNOWN"})
REASONS = frozenset({
    "APPLIED", "DB_CONNECTION_FAILED", "LIVE_CHECK_FAILED", "LOCK_NOT_ACQUIRED",
    "LOCK_NOT_HELD", "APPROVAL_TIME_INVALID", "APPLY_OUTCOME_UNKNOWN",
    "LOCK_RELEASE_FAILED", "CLEANUP_FAILED", "AUDIT_WRITE_FAILED",
})


class AuditRejected(Exception):
    """Only stable codes, never underlying I/O exceptions."""


@dataclass(frozen=True, repr=False)
class AuditClaim:
    directory: Path


def _digest(value: str) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _publish(directory: Path, name: str, data: dict) -> None:
    temporary = directory / (name + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, allow_nan=False, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    # Never replace a pre-existing completion or start record.
    os.link(temporary, directory / name)
    if not _sync_directory(directory):
        raise ValueError
    # Preserve the temporary hardlink as additional incomplete-run evidence.


@dataclass(frozen=True, repr=False)
class FileApplyAudit:
    root: Path

    def consume(
        self, approval_id: str, *, manifest_sha256: str, evidence_sha256: str,
    ) -> AuditClaim:
        """Reserve atomically BEFORE connecting. Any partial claim burns the ID.

        mkdir is the exclusion point, not a prior read/list. A digest of the ID
        is the directory key so a supplied identifier never becomes a path.
        A returned claim requires file AND directory synchronization success.
        """
        try:
            if (
                type(approval_id) is not str or not approval_id
                or not _digest(manifest_sha256) or not _digest(evidence_sha256)
            ):
                raise ValueError
            root = _validated_root(self.root)
            # Fail before reserving/writing on unsupported Windows storage.
            if not _sync_directory(root):
                raise ValueError
            directory = root / sha256(approval_id.encode("utf-8")).hexdigest()
            try:
                directory.mkdir(mode=0o700, exist_ok=False)
            except FileExistsError:
                raise AuditRejected("APPROVAL_ALREADY_USED") from None
            if not _sync_directory(root):
                raise ValueError
            _publish(directory, "started.json", {
                "schema_version": 1, "approval_id_sha256": directory.name,
                "manifest_sha256": manifest_sha256,
                "evidence_sha256": evidence_sha256,
                "started_at_utc": datetime.now(UTC).isoformat(),
            })
            return AuditClaim(directory)
        except AuditRejected:
            raise
        except Exception:
            raise AuditRejected("AUDIT_WRITE_FAILED") from None

    def finish(self, claim: AuditClaim, status: str, reason: str) -> None:
        """Append a single final record. Failure never refunds an approval ID."""
        try:
            root = _validated_root(self.root)
            directory = _validated_root(claim.directory)
            if directory.parent != root or not _digest(directory.name):
                raise ValueError
            if (
                status not in OUTCOMES or reason not in REASONS
                or (status == "APPLIED") != (reason == "APPLIED")
            ):
                raise ValueError
            _publish(directory, "result.json", {
                "schema_version": 1, "status": status, "reason_code": reason,
                "finished_at_utc": datetime.now(UTC).isoformat(),
            })
        except Exception:
            raise AuditRejected("AUDIT_WRITE_FAILED") from None
