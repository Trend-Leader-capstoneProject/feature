"""Internal P4 single-candidate binding checks, NOT a frozen P4 interface.

All inputs belong to one caller-supplied immutable byte snapshot. No resolver,
storage lookup, clock, approval, registration issuance or publication occurs.
MATCH describes bindings only: current registration validity, protected C/E
backup, revocation history and independent observation time remain unverified.
"""

from dataclasses import dataclass, field
from typing import Literal

import fr_b02b_observation as observation
import fr_b02b_registration as registration
from fr_b02b_a1_adapter import _load_a1_snapshot_bytes
from fr_b02b_protected_store import PENDING_KEYS


@dataclass(frozen=True)
class ExpectedBinding:
    """Comparison values only; none of these values conveys authority."""

    trend_ref: str
    content_ref: str
    review_evidence_id: str
    source_url: str
    local_evidence_id: str
    a1_archive_sha256: str
    observation_sha256: str
    index_sha256: str
    registration_id: str
    registration_sha256: str


@dataclass(frozen=True)
class BindingResult:
    binding_status: Literal["MATCH", "BLOCKED", "UNVERIFIED"]
    reason: str
    operational_handoff: str = field(default="HOLD", init=False)
    observation_time: str = field(default="HOLD", init=False)
    publish_authorization: str = field(default="NONE", init=False)


def verify_binding(*, a1_archive_bytes: bytes, observation_bytes: bytes,
                   index_bytes: bytes, expected: ExpectedBinding,
                   registration_bytes: bytes | None) -> BindingResult:
    """Compare A1, local observation, expected item and registration bytes.

    registration_sha256 must pin the very manifest returned by protected-ref
    resolution, not merely its ID. That resolver's trustworthiness is outside
    this function. Missing registration is UNVERIFIED; malformed or mismatched
    supplied evidence is BLOCKED. Every result keeps operational/time HOLD.
    ACCEPTED (even in a valid manifest) is never operational approval evidence.
    """
    try:
        if not isinstance(expected, ExpectedBinding):
            raise TypeError("invalid comparison values")
        for name in expected.__dataclass_fields__:
            if not isinstance(getattr(expected, name), str) or not getattr(expected, name):
                raise ValueError("invalid comparison field")
        for raw in (observation_bytes, index_bytes):
            if not isinstance(raw, bytes) or not 0 < len(raw) <= observation.MAX_RECORD_BYTES:
                raise ValueError("invalid observation bytes")
        snapshot = _load_a1_snapshot_bytes(a1_archive_bytes)
        record = observation._validate_records(
            snapshot, observation_bytes, index_bytes, expected.local_evidence_id)
        for key in observation.BINDING_KEYS:
            if getattr(expected, key) != getattr(snapshot, key):
                raise ValueError("candidate binding mismatch")
        for key, raw in (("a1_archive_sha256", a1_archive_bytes),
                         ("observation_sha256", observation_bytes), ("index_sha256", index_bytes)):
            if getattr(expected, key) != observation.digest(raw):
                raise ValueError("artifact digest mismatch")
        registration._id(expected.registration_id)
        if registration_bytes is None:
            return BindingResult("UNVERIFIED", "REGISTRATION_MISSING")
        manifest = registration._parse(registration_bytes, registration.KEYS)
        if (manifest["registration_id"] != expected.registration_id
                or observation.digest(registration_bytes) != expected.registration_sha256):
            raise ValueError("registration identity/fingerprint mismatch")
        evidence = observation.VerifiedObservation(snapshot, record, observation_bytes, index_bytes)
        # Adapt the frozen manifest's own decision fields to the existing pure
        # validator. This is NOT a new review decision or proof of its authority.
        pending_bytes = observation.canonical_bytes({key: manifest[key] for key in PENDING_KEYS})
        registration._validate_manifest_bindings(registration_bytes, evidence, pending_bytes)
        return BindingResult("MATCH", "BINDINGS_MATCH_OPERATIONS_UNVERIFIED")
    except (ValueError, TypeError, OverflowError, RecursionError):
        # Never expose untrusted fields, local paths or reviewer SID in diagnostics.
        return BindingResult("BLOCKED", "BINDING_MISMATCH_OR_INVALID_EVIDENCE")
