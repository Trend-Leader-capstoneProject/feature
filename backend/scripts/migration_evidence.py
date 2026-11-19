"""Independent B-2 JSON v1 writer. No DB reads, approval or CLI exit mapping.

Input must already be secret-free structured evidence, never raw settings or
exceptions. Validation is defense in depth, not arbitrary secret detection.
The operator must protect the existing root and its ancestors against mutation.
Windows ACLs and mount durability require deployment-specific verification.
"""

import json
import os
import re
import stat
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

REASON_CODES = frozenset(
    {
        "SETTINGS_INVALID",
        "ENV_CONFLICT",
        "DB_CONNECTION_FAILED",
        "READ_ONLY_NOT_ESTABLISHED",
        "TARGET_MISMATCH",
        "SCHEMA_INDETERMINATE",
        "OBSERVATION_FAILED",
        "EVIDENCE_WRITE_FAILED",
    }
)
FIELDS = frozenset(
    {
        "schema_version",
        "evidence_id",
        "observed_at_utc",
        "inspection_status",
        "schema_state",
        "configured_target",
        "observed_target",
        "current_revisions",
        "reason_codes",
        "checks",
        "image_identity_verification_status",
    }
)
CONFIGURED_FIELDS = frozenset({"host", "port", "database", "user"})
OBSERVED_FIELDS = frozenset(
    {
        "database",
        "current_user",
        "server_version",
        "database_charset",
        "database_collation",
    }
)
SCHEMA_STATES = frozenset(
    {
        "VERSIONED_OBSERVED",
        "UNVERSIONED_EMPTY_CANDIDATE",
        "INDETERMINATE",
    }
)
_SENSITIVE = re.compile(
    r"password|secret|token|jwt|exception|traceback|environment|dump|://|"
    r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EvidenceWriteResult:
    success: bool = False
    report_path: Path | None = None
    directory_synced: bool = False
    reason_codes: tuple[str, ...] = ("EVIDENCE_WRITE_FAILED",)


def new_evidence_id() -> str:
    return str(uuid4())


def _text(value: object) -> bool:
    return (
        type(value) is str
        and 0 < len(value) <= 512
        and all(character.isprintable() for character in value)
        and not _SENSITIVE.search(value)
    )


def _checks(value: object, depth: int = 0) -> bool:
    """Structured checks only: no free-form diagnostic strings.

    This writer accepts nested boolean/null checks and frozen reason codes.
    It does not define which checks the future orchestration layer performs.
    """
    if depth > 8:
        return False
    if value is None or type(value) is bool:
        return True
    if type(value) is str:
        return value in REASON_CODES
    if type(value) is list:
        return all(_checks(item, depth + 1) for item in value)
    if type(value) is dict:
        return all(
            _text(key)
            and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", key)
            and _checks(item, depth + 1)
            for key, item in value.items()
        )
    return False


def _validate_report(data: dict) -> None:
    if type(data) is not dict or data.keys() != FIELDS:
        raise ValueError
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError
    identifier = data["evidence_id"]
    if type(identifier) is not str or str(UUID(identifier)) != identifier:
        raise ValueError
    timestamp = data["observed_at_utc"]
    if not _text(timestamp):
        raise ValueError
    parsed = datetime.fromisoformat(timestamp)
    if "T" not in timestamp or parsed.utcoffset() != timedelta(0):
        raise ValueError
    if data["inspection_status"] not in {"OBSERVED", "INDETERMINATE", "ERROR"}:
        raise ValueError
    if data["schema_state"] is not None and data["schema_state"] not in SCHEMA_STATES:
        raise ValueError
    configured = data["configured_target"]
    observed = data["observed_target"]
    for target, keys in ((configured, CONFIGURED_FIELDS), (observed, OBSERVED_FIELDS)):
        if type(target) is not dict or target.keys() != keys:
            raise ValueError
        for key, value in target.items():
            if key == "port":
                if value is not None and (
                    type(value) is not int or not 1 <= value <= 65535
                ):
                    raise ValueError
            elif value is not None and not _text(value):
                raise ValueError
    reasons = data["reason_codes"]
    if type(reasons) is not list or any(code not in REASON_CODES for code in reasons):
        raise ValueError
    if (
        data["schema_state"] is None
        or any(value is None for value in (*configured.values(), *observed.values()))
    ) and not reasons:
        raise ValueError
    revisions = data["current_revisions"]
    if type(revisions) is not list or any(
        revision is not None
        and (not _text(revision) or not re.fullmatch(r"[A-Za-z0-9_]{1,64}", revision))
        for revision in revisions
    ):
        raise ValueError
    if type(data["checks"]) not in (dict, list) or not _checks(data["checks"]):
        raise ValueError
    if data["image_identity_verification_status"] != "NOT_VERIFIED":
        raise ValueError


def _validated_root(root: str | Path) -> Path:
    path = Path(root)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError
    for component in (*reversed(path.parents), path):
        info = component.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            # Reject Windows reparse points too, including junctions.
            raise ValueError
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or not os.access(path, os.W_OK | os.X_OK):
        raise ValueError
    if os.name == "posix" and (info.st_uid != os.geteuid() or info.st_mode & 0o077):
        raise ValueError
    return path


def evidence_root_available(root: str | Path) -> bool:
    """Non-mutating pre-DB check; not proof of ACLs, disk space or persistence."""
    try:
        _validated_root(root)
        return True
    except Exception:
        return False


def _sync_directory(path: Path) -> bool:
    if os.name == "nt":
        # Python's portable directory fsync is unavailable here. Never claim it.
        return False
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return True


def write_evidence(root: str | Path, data: dict) -> EvidenceWriteResult:
    """Reserve once, write/fsync, publish without replacement, sync directories.

    No retries or failure cleanup. Any reserved ID is consumed even if writing
    fails or the process dies. A report filename alone is not a completion
    receipt: sync/cleanup can still fail after publication. Investigate those
    runs separately. Only the returned success confirms this call completed.
    """
    try:
        _validate_report(data)
        # Detach caller-owned mutable data before reserving a directory or doing
        # any I/O. Validate the detached JSON too if mutation raced serialization.
        serialized = json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2)
        snapshot = json.loads(serialized)
        _validate_report(snapshot)
        root_path = _validated_root(root)
        directory = root_path / snapshot["evidence_id"]
        directory.mkdir(mode=0o700, exist_ok=False)
        _sync_directory(root_path)
        temporary = directory / "report.tmp"
        final = directory / "report.json"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            stream = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")
        except BaseException:
            os.close(descriptor)
            raise
        with stream:
            json.dump(snapshot, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        # Atomic no-clobber creation, including a concurrent destination claim.
        # Hard links must be supported on this filesystem; no copy/replace fallback.
        os.link(temporary, final)
        synced = _sync_directory(directory)
        os.unlink(temporary)
        synced = _sync_directory(directory) and synced
        if final.read_bytes() != (serialized + "\n").encode("utf-8"):
            raise ValueError
        return EvidenceWriteResult(True, final, synced, ())
    except Exception:
        # Return only a fixed reason; no raw exception, path, payload or logging.
        return EvidenceWriteResult()
