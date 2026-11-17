"""Offline B-3 Manifest validation/comparison; never an approval issuer.

JSON v1 below is an implementation format, not a frozen operational file or
audit-store contract. Trusted context must come from independent operator
review/verification, never from hashing or copying the submitted inputs and
calling them trusted. Content pins detect changes relative to that review;
they are not signatures. No environment, DB connection, writes or apply path.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path

from alembic.script import ScriptDirectory

from scripts.migration_evidence import _text, _validate_report
from scripts.migration_preflight import classify_schema_state

MANIFEST_FIELDS = frozenset({
    "schema_version", "approval_id", "environment", "deployment_project",
    "db_host", "db_port", "db_name", "expected_db_account",
    "expected_from_revision", "target_revision", "backend_image_digest",
    "preflight_evidence_id", "backup_or_empty_db_evidence_id", "approved_by",
    "approved_at", "expires_at",
})
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_HASH = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, repr=False)
class RecoveryConfirmation:
    """Independent review of backup+restore or verified empty DB/Bootstrap.

    Binding to the reviewed Manifest bytes scopes the confirmation to its
    exact target, account, revisions, approval and referenced recovery ID.
    This class neither verifies nor creates the underlying recovery evidence.
    """

    evidence_id: str
    kind: str  # BACKUP_RESTORE or EMPTY_BOOTSTRAP (implementation vocabulary)
    manifest_sha256: str


@dataclass(frozen=True, repr=False)
class ComparisonContext:
    """Trusted review facts, not user-supplied JSON or an approval credential.

    None means unverified/unavailable and fails closed. An audit snapshot can
    only detect known reuse; it cannot reserve an ID against concurrent apply.
    A future protected, atomic pre-APPLY use record remains mandatory.
    """

    environment: str
    deployment_project: str
    manifest_sha256: str | None = None
    evidence_sha256: str | None = None
    verified_image_digest: str | None = None
    used_approval_ids: frozenset[str] | None = None
    recovery: RecoveryConfirmation | None = None


@dataclass(frozen=True)
class ValidationResult:
    """Only fixed codes leave validation; no input/exception reflection."""

    reason_codes: tuple[str, ...]

    @property
    def matches(self) -> bool:
        return not self.reason_codes

    @property
    def apply_enabled(self) -> bool:
        return False


class _Rejected(Exception):
    pass


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise _Rejected(reason)


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _invalid_constant(_value: str) -> None:
    raise ValueError


def _json(payload: bytes) -> dict:
    if type(payload) is not bytes:
        raise ValueError
    data = json.loads(
        payload.decode("utf-8"), object_pairs_hook=_pairs,
        parse_constant=_invalid_constant,
    )
    if type(data) is not dict:
        raise ValueError
    return data


def _instant(value: str) -> datetime:
    if not _text(value) or "T" not in value:
        raise ValueError
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() != timedelta(0):
        raise ValueError
    return parsed


def _repository_lineage() -> tuple[str, ...]:
    """Read actual revision metadata; never run env.py or migration functions."""
    directory = Path(__file__).resolve().parents[1] / "alembic"
    scripts = ScriptDirectory(str(directory))
    if len(scripts.get_heads()) != 1:
        raise ValueError
    revisions = list(scripts.walk_revisions())  # newest first
    if not revisions:
        raise ValueError
    for index, revision in enumerate(revisions):
        parent = revisions[index + 1].revision if index + 1 < len(revisions) else None
        if revision.down_revision != parent or revision.dependencies:
            raise ValueError  # branching/merging/dependencies require review
    return tuple(revision.revision for revision in revisions)


def _manifest(payload: bytes, now: datetime) -> tuple[dict, tuple[str, ...]]:
    try:
        data = _json(payload)
        if data.keys() != MANIFEST_FIELDS:
            raise ValueError
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise ValueError
        if type(data["db_port"]) is not int or not 1 <= data["db_port"] <= 65535:
            raise ValueError
        for key, value in data.items():
            if key in {"schema_version", "db_port"}:
                continue
            # Explicit null represents no prior revision ONLY for a separately
            # confirmed empty Bootstrap. Missing fields are still invalid.
            if key == "expected_from_revision" and value is None:
                continue
            if not _text(value) or value != value.strip():
                raise ValueError
        user, separator, host = data["expected_db_account"].rpartition("@")
        if not user or not separator or not host:
            raise ValueError
        if not _DIGEST.fullmatch(data["backend_image_digest"]):
            raise ValueError
        if not isinstance(now, datetime) or now.utcoffset() != timedelta(0):
            raise ValueError
        approved = _instant(data["approved_at"])
        expires = _instant(data["expires_at"])
    except Exception:
        raise _Rejected("MANIFEST_INVALID") from None
    _require(approved <= now < expires, "APPROVAL_TIME_INVALID")
    try:
        lineage = _repository_lineage()
    except Exception:
        raise _Rejected("REVISION_LINEAGE_UNAVAILABLE") from None
    before = data["expected_from_revision"]
    target = data["target_revision"]
    _require(target in lineage, "REVISION_INVALID")
    if before is not None:
        _require(before in lineage, "REVISION_INVALID")
        _require(lineage.index(target) <= lineage.index(before), "REVISION_INVALID")
    return data, lineage


def validate_manifest(payload: bytes, *, now: datetime) -> ValidationResult:
    """Validate A-2 semantics/time/actual revisions; does not issue approval."""
    try:
        _manifest(payload, now)
        return ValidationResult(())
    except _Rejected as error:
        return ValidationResult((error.args[0],))
    except Exception:
        return ValidationResult(("MANIFEST_INVALID",))


def _pin(payload: bytes, expected: str | None) -> bool:
    return (
        type(expected) is str and bool(_HASH.fullmatch(expected))
        and sha256(payload).hexdigest() == expected
    )


def compare_approval(
    manifest_payload: bytes, evidence_payload: bytes,
    *, context: ComparisonContext, now: datetime,
) -> ValidationResult:
    """Compare detached bytes to independent review facts without any writes.

    Even a matching result is neither operator authentication nor permission
    to APPLY. It does not verify DB server uniqueness, current DB state,
    image provenance, file ACLs, recovery evidence or audit-store durability.
    Those facts must be independently established by future operational
    adapters. Guard apply remains MODE_NOT_ENABLED.
    """
    try:
        manifest, lineage = _manifest(manifest_payload, now)
        _require(
            _pin(manifest_payload, context.manifest_sha256)
            and _pin(evidence_payload, context.evidence_sha256),
            "CONTENT_PIN_MISMATCH",
        )
        try:
            evidence = _json(evidence_payload)
            _validate_report(evidence)  # unchanged B-2 JSON v1 incl. NOT_VERIFIED
            observed_at = _instant(evidence["observed_at_utc"])
        except Exception:
            raise _Rejected("EVIDENCE_INVALID") from None
        _require(
            evidence["inspection_status"] == "OBSERVED"
            and not evidence["reason_codes"]
            and observed_at <= _instant(manifest["approved_at"]),
            "EVIDENCE_NOT_OBSERVED",
        )
        _require(
            manifest["preflight_evidence_id"] == evidence["evidence_id"],
            "EVIDENCE_ID_MISMATCH",
        )
        configured = evidence["configured_target"]
        observed = evidence["observed_target"]
        _require(
            manifest["environment"] == context.environment
            and manifest["deployment_project"] == context.deployment_project
            and (manifest["db_host"], manifest["db_port"], manifest["db_name"])
            == (configured["host"], configured["port"], configured["database"])
            and manifest["db_name"] == observed["database"]
            and manifest["expected_db_account"] == observed["current_user"]
            and manifest["expected_db_account"].rpartition("@")[0]
            == configured["user"],
            "TARGET_MISMATCH",
        )
        checks = evidence["checks"]
        _require(
            type(checks) is dict
            and type(checks.get("version_table_visible")) is bool
            and type(checks.get("business_objects_visible")) is bool,
            "EVIDENCE_INVALID",
        )
        state = classify_schema_state(
            version_table_visible=checks["version_table_visible"],
            current_revisions=evidence["current_revisions"],
            business_objects_visible=checks["business_objects_visible"],
            known_revisions=lineage,
        )
        _require(state == evidence["schema_state"], "SCHEMA_NOT_COMPARABLE")
        before = manifest["expected_from_revision"]
        if state == "VERSIONED_OBSERVED":
            _require(
                before is not None and evidence["current_revisions"] == [before],
                "REVISION_MISMATCH",
            )
            recovery_kind = "BACKUP_RESTORE"
        elif state == "UNVERSIONED_EMPTY_CANDIDATE":
            _require(before is None, "REVISION_MISMATCH")
            recovery_kind = "EMPTY_BOOTSTRAP"
        else:
            raise _Rejected("SCHEMA_NOT_COMPARABLE")
        reasons = []
        if context.verified_image_digest != manifest["backend_image_digest"]:
            reasons.append("IMAGE_NOT_VERIFIED")
        recovery = context.recovery
        if not (
            isinstance(recovery, RecoveryConfirmation)
            and recovery.evidence_id == manifest["backup_or_empty_db_evidence_id"]
            and recovery.evidence_id != evidence["evidence_id"]
            and recovery.kind == recovery_kind
            and recovery.manifest_sha256 == context.manifest_sha256
        ):
            reasons.append("RECOVERY_NOT_VERIFIED")
        used = context.used_approval_ids
        if type(used) is not frozenset or any(
            not _text(item) or item != item.strip() for item in used
        ):
            reasons.append("AUDIT_UNAVAILABLE")
        elif manifest["approval_id"] in used:
            reasons.append("APPROVAL_ALREADY_USED")
        return ValidationResult(tuple(reasons))
    except _Rejected as error:
        return ValidationResult((error.args[0],))
    except Exception:
        return ValidationResult(("COMPARISON_FAILED",))
