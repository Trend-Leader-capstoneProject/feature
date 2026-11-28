"""AP-3C-1 review-only decision contract; no Writer or authorization path."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Literal, Protocol

from app.trend_collection.godot_release_collector import (
    REPO,
    CollectionError,
    ReleaseEvidence,
)
from app.trend_collection.rule_first_preview import build_rule_first_preview

POLICY_VERSION = "AP3C1_V1"
PROFILE = "AUTO-TREND-MVP"
SYNTHETIC_PROFILE = "AP3C1_SYNTHETIC_ONLY"
BATCH_SIZE = 1
INTERVAL_SECONDS = 6 * 60 * 60
DecisionState = Literal["AUTO_ELIGIBLE", "DEFERRED", "SKIPPED", "BLOCKED"]


@dataclass(frozen=True, slots=True)
class SourcePolicy:
    source_id: str
    access: str
    storage: str
    display: str
    ai_transfer: str


# Read-only PoC evidence is not a grant of operational rights.
GODOT_POLICY = SourcePolicy(REPO, "UNVERIFIED", "UNVERIFIED", "UNVERIFIED", "DENIED")


def _canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value) -> str:
    return sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class ContentSnapshot:
    profile_id: str
    policy_version: str
    target: str
    candidate_identity: str
    evidence_ref: str
    title: str
    normalized_title: str
    summary: str
    source_url: str
    external_id: str
    source_key: str
    platform: str
    parent_code: str
    child_name: str
    observed_at_utc: str
    source_published_at: str
    proposed_status: str
    is_primary: bool = True
    thumbnail_url: str | None = None
    source_title: None = None

    @property
    def content_digest(self) -> str:
        return _digest(asdict(self))


class PersistableSnapshot(Protocol):
    """Read-only structural contract for common Writer input."""

    @property
    def profile_id(self) -> str: ...

    @property
    def policy_version(self) -> str: ...

    @property
    def target(self) -> str: ...

    @property
    def candidate_identity(self) -> str: ...

    @property
    def evidence_ref(self) -> str: ...

    @property
    def title(self) -> str: ...

    @property
    def normalized_title(self) -> str: ...

    @property
    def summary(self) -> str: ...

    @property
    def source_url(self) -> str: ...

    @property
    def external_id(self) -> str: ...

    @property
    def source_key(self) -> str: ...

    @property
    def platform(self) -> str: ...

    @property
    def parent_code(self) -> str: ...

    @property
    def child_name(self) -> str: ...

    @property
    def observed_at_utc(self) -> str: ...

    @property
    def proposed_status(self) -> str: ...

    @property
    def is_primary(self) -> bool: ...

    @property
    def thumbnail_url(self) -> str | None: ...

    @property
    def content_digest(self) -> str: ...


@dataclass(frozen=True, slots=True)
class PopularitySnapshot:
    """IGDB observation; independent of legacy release-event digest."""

    profile_id: str
    policy_version: str
    target: str
    candidate_identity: str
    evidence_ref: str
    title: str
    normalized_title: str
    summary: str
    source_url: str
    external_id: str
    source_key: str
    platform: str
    parent_code: str
    child_name: str
    observed_at_utc: str
    calculated_at_utc: str
    rank: int
    metric_id: int
    proposed_status: str
    is_primary: bool = True
    thumbnail_url: str | None = None
    source_title: None = None

    @property
    def content_digest(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    profile_id: str
    policy_version: str
    decision: DecisionState
    reason_codes: tuple[str, ...]
    evaluated_at: str | None
    snapshot: ContentSnapshot | None = None

    # Fixed outputs; not constructor inputs or an approval token.
    @property
    def publish_authorization(self) -> Literal["NONE"]:
        return "NONE"


def _decision(state, reasons, now=None, snapshot=None, *, profile=PROFILE):
    return PolicyDecision(profile, POLICY_VERSION, state, tuple(reasons),
                          now, snapshot)


def evaluate_release(evidence: ReleaseEvidence, observed_at: datetime,
                     preview: dict) -> PolicyDecision:
    """Reconstruct allowed content; caller flags cannot grant source rights."""
    try:
        expected = build_rule_first_preview(evidence, observed_at)
    except CollectionError as exc:
        if (str(exc) == "OUTSIDE_PROPOSED_7_DAY_WINDOW"
                and observed_at - evidence.published_at > timedelta(days=7)):
            return _decision("SKIPPED", ("STALE_RELEASE",))
        return _decision("BLOCKED", ("INVALID_RELEASE_EVIDENCE",))
    except (TypeError, ValueError, OverflowError):
        return _decision("BLOCKED", ("INVALID_RELEASE_EVIDENCE",))
    now = observed_at.astimezone(timezone.utc).isoformat()
    try:
        if type(preview) is not dict or _canonical(preview) != _canonical(expected):
            return _decision("BLOCKED", ("PREVIEW_MISMATCH",), now)
    except (TypeError, ValueError, RecursionError, UnicodeError):
        return _decision("BLOCKED", ("PREVIEW_MISMATCH",), now)
    source = expected["proposed_source"]
    category = expected["proposed_category_ref"]
    evidence_ref = _digest({
        "repo": REPO, "id": evidence.release_id, "tag": evidence.tag,
        "prerelease": evidence.prerelease, "url": evidence.url,
        "published_at": evidence.published_at.astimezone(timezone.utc).isoformat(),
    })
    snapshot = ContentSnapshot(
        PROFILE, POLICY_VERSION, "UNBOUND_OPERATIONAL", expected["candidate_identity"],
        evidence_ref, expected["title"], expected["normalized_title"],
        expected["summary"], source["source_url"], source["external_id"],
        sha256(f"ETC:{source['external_id']}".encode("utf-8")).hexdigest(),
        "ETC", category["parent_code"], category["child_name"], now,
        evidence.published_at.astimezone(timezone.utc).isoformat(), "ACTIVE",
    )
    # No reader of trusted rights evidence exists in AP-3C-1. Keep fail closed.
    reasons = ["ACTIVE_CATEGORY_UNVERIFIED", "INDEPENDENT_AUTHORITY_UNVERIFIED"]
    if (GODOT_POLICY.access, GODOT_POLICY.storage, GODOT_POLICY.display) != (
        "ALLOWED", "ALLOWED", "ALLOWED",
    ):
        reasons.insert(0, "SOURCE_RIGHTS_UNVERIFIED")
    return _decision("DEFERRED", reasons, now, snapshot)


def synthetic_fixture_decision() -> PolicyDecision:
    """Fixed isolated contract example; no input, no real source or DB target."""
    identity = "synthetic-ap3:policy:1"
    stamp = "2000-01-01T00:00:00+00:00"
    snapshot = ContentSnapshot(
        SYNTHETIC_PROFILE, POLICY_VERSION, "ISOLATED_SYNTHETIC_ONLY", identity,
        _digest({"fixture": identity}), "Synthetic AP3 policy fixture",
        "synthetic ap3 policy fixture", "Synthetic fixture only.",
        "https://example.invalid/ap3/policy/1", identity,
        sha256(f"ETC:{identity}".encode("utf-8")).hexdigest(),
        "ETC", "IT_DIGITAL", "소프트웨어·앱", stamp, stamp, "HIDDEN",
    )
    return _decision("AUTO_ELIGIBLE", ("FIXED_SYNTHETIC_FIXTURE_ONLY",),
                     stamp, snapshot, profile=SYNTHETIC_PROFILE)


def verify_release_decision(decision: PolicyDecision, evidence: ReleaseEvidence,
                            observed_at: datetime, preview: dict) -> bool:
    """Exact re-projection check; not independent authentication or approval."""
    if type(decision) is not PolicyDecision:
        return False
    expected = evaluate_release(evidence, observed_at, preview)
    try:
        return _canonical(asdict(decision)) == _canonical(asdict(expected))
    except (TypeError, ValueError, RecursionError, UnicodeError):
        return False


def writer_boundary(decision: object) -> str:
    """No DB connector exists here, even for a forged or synthetic decision."""
    return "BLOCKED_AP3C1_NO_WRITER_AUTHORITY"


def build_policy_preview(evidence: ReleaseEvidence, observed_at: datetime) -> dict:
    """Read-only Collector projection; never export an executable snapshot."""
    preview = build_rule_first_preview(evidence, observed_at)
    result = evaluate_release(evidence, observed_at, preview)
    return {**preview, "policy_profile": result.profile_id,
            "policy_version": result.policy_version,
            "policy_decision": result.decision,
            "policy_reason_codes": list(result.reason_codes),
            "writer_boundary": writer_boundary(result)}
