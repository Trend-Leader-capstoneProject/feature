"""Phase 4A local attestation and integrity only. No approval or publication.

The local clock, actor, content rights and browser rendering are NOT certified.
Matching SHA-256 files are not signatures or an immutable operational journal.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fr_b02b_a1_adapter import A1Snapshot, load_a1_snapshot, read_a1_archive

RECORDED = "LOCAL_OBSERVATION_RECORDED_REVIEW_HOLD"
MAX_RECORD_BYTES = 65_536  # Exceeds the bounded A1 reference/URL field sizes.
RECORD_CONSTANTS = {
    "schema": "FR_B02B_LOCAL_OBSERVATION_V1",
    "profile": "MVP-A",
    "source_title_origin": "EDITORIAL_LABEL",
    "event_kind": "MANUAL_SOURCE_COLLECTION",
    "observation_method": "HUMAN_BROWSER_ATTESTATION",
    "attestation": "USER_CONFIRMED",
    "clock_source": "LOCAL_SYSTEM_CLOCK",
    "observer_ref": "UNVERIFIED_LOCAL_OPERATOR",
    "actor_assurance": "UNVERIFIED",
    "review_result": "HOLD",
    "publish_authorization": "NONE",
}
BINDING_KEYS = ("trend_ref", "content_ref", "review_evidence_id", "source_url")
RECORD_KEYS = frozenset(RECORD_CONSTANTS) | frozenset(BINDING_KEYS) | {
    "evidence_id", "a1_archive_sha256", "confirmed_at_utc", "record_created_at_utc",
}
INDEX_KEYS = frozenset({
    "schema", "evidence_id", "artifact_file", "artifact_sha256", "trend_ref",
    "content_ref", "a1_archive_sha256", "status",
})
EVIDENCE_ID = re.compile(r"LOCAL-OBS-[0-9a-f]{32}\Z")
UTC_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|\+00:00)\Z"
)


class ObservationError(ValueError):
    """Fail closed without modifying approval inputs or promoting a local draft."""


def canonical_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8") + b"\n"


def digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def capture_confirmation_time() -> datetime:
    """Called immediately after exact YES; never use an approval/publish date."""
    try:
        value = utc_now()
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise ValueError("timezone-aware clock required")
        return value.astimezone(timezone.utc)
    except Exception as exc:
        raise ObservationError("invalid or unavailable UTC clock") from exc


def _is_reparse_point(path: Path) -> bool:
    info = path.lstat()
    return bool(stat.S_ISLNK(info.st_mode) or (
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    ))


def _safe_local_path(path: Path) -> Path:
    """Check lexical ancestors before resolving; .git files include worktrees.

    Permission/indeterminate errors propagate as blocking errors. This does not
    promise protection against all hostile filesystem races or certify ACLs.
    """
    if any(os.environ.get(key) for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR")):
        raise ObservationError("Git environment overrides prevent safe path determination")
    if ".." in path.parts:
        raise ObservationError("ambiguous local record path")
    path = path.absolute()
    for part in (*reversed(path.parents), path):
        if part.name.lower() == ".git":
            raise ObservationError("records must be outside Git working trees")
        try:
            if _is_reparse_point(part):
                raise ObservationError("symlink/reparse local paths are forbidden")
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISDIR(info.st_mode):
            try:
                (part / ".git").lstat()
            except FileNotFoundError:
                pass
            else:
                raise ObservationError("records must be outside Git working trees")
        elif part != path:
            raise ObservationError("non-directory record path ancestor")
    return path


def validate_output_dir(output_dir: Path, archive_path: Path) -> Path:
    root = _safe_local_path(output_dir)
    if root == archive_path.absolute():
        raise ObservationError("output cannot be the input archive")
    try:
        info = root.lstat()
    except FileNotFoundError:
        return root
    if not stat.S_ISDIR(info.st_mode):
        raise ObservationError("output must be a directory")
    if not os.access(root, os.W_OK | os.X_OK):
        raise ObservationError("output directory is not accessible")
    return root


def require_observation_candidate(snapshot: A1Snapshot) -> None:
    # A1 NONE remains supported by existing inspect commands; only the new
    # observation path requires the frozen EDITORIAL_LABEL subset.
    if snapshot.source_title_origin != "EDITORIAL_LABEL":
        raise ObservationError("observation requires EDITORIAL_LABEL")


def _event_id(value: Any) -> str:
    if not isinstance(value, str) or not EVIDENCE_ID.fullmatch(value):
        raise ObservationError("invalid local observation ID")
    parsed = uuid.UUID(hex=value.removeprefix("LOCAL-OBS-"))
    if parsed.version != 4 or parsed.variant != uuid.RFC_4122:
        raise ObservationError("UUID4 observation ID required")
    return value


def _parse_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ObservationError("duplicate local JSON key")
        obj[key] = value
    return obj


def _invalid_constant(_value: str) -> None:
    raise ObservationError("nonfinite local JSON value")


def _parse(raw: bytes, keys: frozenset[str]) -> dict[str, Any]:
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_parse_pairs,
                         parse_constant=_invalid_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ObservationError("invalid local JSON") from exc
    if not isinstance(obj, dict) or set(obj) != keys:
        raise ObservationError("unexpected or missing local record fields")
    if any(not isinstance(v, str) for v in obj.values()):
        raise ObservationError("local record fields must be strings")
    if canonical_bytes(obj) != raw:
        raise ObservationError("noncanonical local JSON")
    return obj


def _timestamp(value: str) -> datetime:
    if not UTC_TIMESTAMP.fullmatch(value):
        raise ObservationError("UTC ISO8601 timestamp required")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ObservationError("invalid UTC timestamp") from exc
    if result.utcoffset() != timedelta(0):
        raise ObservationError("UTC timestamp required")
    return result


def _validate_records(snapshot: A1Snapshot, record_raw: bytes, index_raw: bytes,
                      directory_id: str) -> dict[str, str]:
    require_observation_candidate(snapshot)
    record = _parse(record_raw, RECORD_KEYS)
    index = _parse(index_raw, INDEX_KEYS)
    for key, value in RECORD_CONSTANTS.items():
        if record[key] != value:
            raise ObservationError("unsafe local observation state: " + key)
    event_id = _event_id(record["evidence_id"])
    if event_id != directory_id:
        raise ObservationError("observation ID/directory mismatch")
    for key in BINDING_KEYS:
        if record[key] != getattr(snapshot, key):
            raise ObservationError("A1 snapshot binding mismatch: " + key)
    if record["a1_archive_sha256"] != digest(snapshot.archive_bytes):
        raise ObservationError("A1 ZIP byte digest mismatch")
    if _timestamp(record["record_created_at_utc"]) < _timestamp(record["confirmed_at_utc"]):
        raise ObservationError("local clock moved backwards")
    expected_index = {
        "schema": "FR_B02B_LOCAL_INDEX_V1",
        "evidence_id": event_id,
        "artifact_file": "observation.json",
        "artifact_sha256": digest(record_raw),
        "trend_ref": record["trend_ref"],
        "content_ref": record["content_ref"],
        "a1_archive_sha256": record["a1_archive_sha256"],
        "status": RECORDED,
    }
    if index != expected_index:
        raise ObservationError("local index digest/reference/state mismatch")
    return {"status": "PASS_LOCAL_INTEGRITY_ONLY", "evidence_id": event_id,
            "publish_authorization": "NONE"}


def _read_record_file(path: Path) -> bytes:
    _safe_local_path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_RECORD_BYTES:
        raise ObservationError("invalid or oversized local record file")
    with path.open("rb") as file:
        raw = file.read(MAX_RECORD_BYTES + 1)
    if len(raw) > MAX_RECORD_BYTES:
        raise ObservationError("oversized local record file")
    return raw


def verify_observation(archive_path: Path, record_dir: Path) -> dict[str, str]:
    """Read only; do not repair missing files, rehash, or authenticate an actor."""
    folder = _safe_local_path(record_dir)
    _event_id(folder.name)
    if not stat.S_ISDIR(folder.lstat().st_mode):
        raise ObservationError("local record directory missing")
    snapshot = load_a1_snapshot(archive_path)
    result = _validate_records(
        snapshot, _read_record_file(folder / "observation.json"),
        _read_record_file(folder / "index.json"), folder.name,
    )
    if read_a1_archive(archive_path) != snapshot.archive_bytes:
        raise ObservationError("A1 ZIP changed during verification")
    return result


def _write_fsynced(path: Path, raw: bytes) -> None:
    with path.open("xb") as file:
        file.write(raw)
        file.flush()
        os.fsync(file.fileno())


def record_observation(snapshot: A1Snapshot, archive_path: Path, output_dir: Path,
                       confirmed_at: datetime) -> dict[str, str]:
    """Persist a new HOLD draft, then independently read and verify its bytes.

    Remnants of failed persistence/verification are deliberately left for manual
    investigation, never auto-discovered/accepted. No durable journal guarantee.
    """
    require_observation_candidate(snapshot)
    root = validate_output_dir(output_dir, archive_path)
    if read_a1_archive(archive_path) != snapshot.archive_bytes:
        raise ObservationError("A1 ZIP changed during confirmation")
    event_id = _event_id("LOCAL-OBS-" + uuid.uuid4().hex)
    # Separate clock sample immediately before assembling the JSON object.
    created_at = capture_confirmation_time()
    if confirmed_at.utcoffset() is None or created_at < confirmed_at:
        raise ObservationError("invalid or backwards local clock")
    record = {
        **RECORD_CONSTANTS,
        **{key: getattr(snapshot, key) for key in BINDING_KEYS},
        "evidence_id": event_id,
        "a1_archive_sha256": digest(snapshot.archive_bytes),
        "confirmed_at_utc": confirmed_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "record_created_at_utc": created_at.isoformat().replace("+00:00", "Z"),
    }
    record_raw = canonical_bytes(record)
    index = {
        "schema": "FR_B02B_LOCAL_INDEX_V1", "evidence_id": event_id,
        "artifact_file": "observation.json", "artifact_sha256": digest(record_raw),
        "trend_ref": snapshot.trend_ref, "content_ref": snapshot.content_ref,
        "a1_archive_sha256": record["a1_archive_sha256"], "status": RECORDED,
    }
    index_raw = canonical_bytes(index)
    _validate_records(snapshot, record_raw, index_raw, event_id)
    root.mkdir(parents=True, exist_ok=True)
    validate_output_dir(root, archive_path)
    destination = root / event_id
    if os.path.lexists(destination):
        raise ObservationError("local observation ID already exists")
    staging = Path(tempfile.mkdtemp(prefix=".obs-staging-", dir=root))
    try:
        _safe_local_path(staging)
        _write_fsynced(staging / "observation.json", record_raw)
        _write_fsynced(staging / "index.json", index_raw)
        if read_a1_archive(archive_path) != snapshot.archive_bytes:
            raise ObservationError("A1 ZIP changed before record finalization")
        validate_output_dir(root, archive_path)
        if os.path.lexists(destination):
            raise ObservationError("local observation ID already exists")
        # Windows rename refuses an existing destination. This is not a claim
        # of complete multiprocess race or hostile-filesystem protection.
        os.rename(staging, destination)
        verify_observation(archive_path, destination)
    except (OSError, ObservationError) as exc:
        raise ObservationError(
            "record storage/verification failed; any remnants remain HOLD for manual investigation"
        ) from exc
    return {"status": RECORDED, "evidence_id": event_id,
            "directory": str(destination), "publish_authorization": "NONE"}
