"""Phase 4B-2 authorization and pending decisions; no protected registration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

import fr_b02b_observation as observation
from fr_b02b_a1_adapter import A1InspectionError
from fr_b02b_observation import ObservationError, _load_verified_observation
from fr_b02b_reviewer_allowlist import (
    AllowlistError, AllowlistNotConfigured, AllowlistSource, require_authorized_sid,
)

if TYPE_CHECKING:
    from fr_b02b_protected_store import (
        MirroredEvidenceStore, MirroredStagedReview, ProtectedEvidenceStore, StagedReview,
    )


class ReviewBlocked(ValueError):
    """A category-only failure; never include raw input or OS diagnostics."""


class ReviewCancelled(ValueError):
    """Explicit cancellation without a review or registration."""


@dataclass(frozen=True)
class ReviewPreview:
    title: str
    summary: str
    source_url: str
    confirmed_at_utc: str
    record_created_at_utc: str
    observer_ref: str
    actor_assurance: str


@dataclass(frozen=True)
class PendingReviewDecision:
    """Memory-only human judgment. This is neither a manifest nor a stored ID."""

    local_evidence_id: str
    reviewer_sid: str
    review_result: str
    decision_reason: str
    reviewed_at_utc: str
    evidence: observation.VerifiedObservation
    publish_authorization: str = "NONE"


def validate_review_choice(choice: str) -> str:
    if not isinstance(choice, str):
        raise ReviewBlocked("invalid review decision")
    choice = choice.strip().upper()
    if not choice:
        raise ReviewCancelled()
    if choice not in ("ACCEPTED", "HOLD", "REJECTED"):
        raise ReviewBlocked("invalid review decision")
    return choice


def _review_clock() -> datetime:
    try:
        value = observation.utc_now()
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise ValueError("aware clock required")
        return value.astimezone(timezone.utc)
    except (OSError, ValueError, OverflowError):
        raise ReviewBlocked("invalid or unavailable review clock") from None


def collect_review_decision(archive_path: Path, record_dir: Path, *,
                            request_decision: Callable[[ReviewPreview], tuple[str, str]] | None,
                            allowlist_source: AllowlistSource | None = None) -> PendingReviewDecision:
    """Internal pending-decision boundary; never a protected registration."""
    sid = prepare_review(archive_path, record_dir, allowlist_source=allowlist_source)
    # Reuse the preflight unchanged, then acquire the validated display/byte set.
    # The final ZIP read in the loader is for change detection, never extraction.
    try:
        evidence = observation._load_verified_observation_snapshot(archive_path, record_dir)
    except ObservationError:
        raise ReviewBlocked("local observation integrity failure") from None
    except A1InspectionError:
        raise ReviewBlocked("A1 ZIP validation failure") from None
    except (OSError, ValueError):
        raise ReviewBlocked("local input failure") from None
    record = evidence.record
    snapshot = evidence.a1_snapshot
    preview = ReviewPreview(snapshot.title, snapshot.summary, snapshot.source_url,
                            record["confirmed_at_utc"], record["record_created_at_utc"],
                            record["observer_ref"], record["actor_assurance"])
    started_at = _review_clock()
    created_at = observation._timestamp(record["record_created_at_utc"])
    if started_at < created_at:
        raise ReviewBlocked("backwards review clock")
    if request_decision is None:
        raise ReviewBlocked("review input unavailable")
    try:
        choice, reason = request_decision(preview)
    except (EOFError, KeyboardInterrupt):
        raise ReviewCancelled() from None
    except OSError:
        raise ReviewBlocked("review input unavailable") from None
    choice = validate_review_choice(choice)
    if not isinstance(reason, str) or len(reason) > 500:
        raise ReviewBlocked("invalid review reason")
    reason = reason.strip()
    if choice in ("HOLD", "REJECTED") and not reason:
        raise ReviewBlocked("review reason required")
    # Only this post-decision sample becomes reviewed_at_utc. The first clock
    # sample detects regression during human input and is never a decision time.
    reviewed_at = _review_clock()
    if reviewed_at < started_at or reviewed_at < created_at:
        raise ReviewBlocked("backwards review clock")
    return PendingReviewDecision(record["evidence_id"], sid, choice, reason,
                                 reviewed_at.isoformat().replace("+00:00", "Z"), evidence)


def require_process_sid() -> str:
    """Resolve identity before any reviewer decision; no fallback identity."""
    from fr_b02b_windows_auth import get_current_process_sid

    try:
        sid = get_current_process_sid()
    except (OSError, ValueError, RuntimeError):
        raise ReviewBlocked("reviewer identity unavailable") from None
    if not isinstance(sid, str) or not sid.strip():
        raise ReviewBlocked("reviewer identity unavailable")
    return sid


def prepare_review(archive_path: Path, record_dir: Path, *,
                   allowlist_source: AllowlistSource | None = None) -> str:
    """Revalidate inputs and return the reviewer identity for the next stage."""
    try:
        _load_verified_observation(archive_path, record_dir)
    except ObservationError:
        raise ReviewBlocked("local observation integrity failure") from None
    except A1InspectionError:
        raise ReviewBlocked("A1 ZIP validation failure") from None
    except (OSError, ValueError, RuntimeError):
        raise ReviewBlocked("local input failure") from None

    sid = require_process_sid()
    try:
        return require_authorized_sid(sid, allowlist_source)
    except AllowlistNotConfigured:
        # Retain the preflight's existing public failure for missing deployment
        # configuration; a successful SID lookup still grants no authorization.
        raise ReviewBlocked("protected review registration is not configured") from None
    except AllowlistError as exc:
        raise ReviewBlocked(str(exc)) from None


def review_register(archive_path: Path, record_dir: Path, *,
                    request_decision: Callable[[ReviewPreview], tuple[str, str]] | None = None
                    ) -> NoReturn:
    """Incomplete protected registration must still fail closed."""
    decision = collect_review_decision(archive_path, record_dir, request_decision=request_decision)
    # No Store/root is configured for the actual CLI. It never stages or reports
    # registration success; tests invoke the internal staging entry explicitly.
    stage_pending_review(decision, archive_path, record_dir)
    raise ReviewBlocked("protected review registration is not configured")


def stage_pending_review(decision: PendingReviewDecision, archive_path: Path,
                         record_dir: Path, *,
                         store: ProtectedEvidenceStore | MirroredEvidenceStore | None = None,
                         allowlist_source: AllowlistSource | None = None
                         ) -> StagedReview | MirroredStagedReview:
    """Internal synthetic staging entry; no operational destination is assumed."""
    if store is None:
        raise ReviewBlocked("protected review registration is not configured")
    from fr_b02b_protected_store import StagingError

    evidence = _revalidate_pending_review(decision, archive_path, record_dir, allowlist_source)
    roots = store.staging_roots
    if not roots or any(not isinstance(root, Path) or not root.is_absolute()
            or archive_path.absolute().is_relative_to(root)
            or record_dir.absolute().is_relative_to(root)
            or root.is_relative_to(record_dir.absolute()) for root in roots):
        raise ReviewBlocked("staging root overlaps inputs or is unconfigured; HOLD")
    pending_bytes = observation.canonical_bytes({
        "local_evidence_id": decision.local_evidence_id,
        "reviewer_sid": decision.reviewer_sid, "review_result": decision.review_result,
        "decision_reason": decision.decision_reason, "reviewed_at_utc": decision.reviewed_at_utc,
        "publish_authorization": "NONE",
        "a1_archive_sha256": observation.digest(evidence.a1_snapshot.archive_bytes),
        "observation_sha256": observation.digest(evidence.record_bytes),
        "index_sha256": observation.digest(evidence.index_bytes),
    })

    def revalidate_input():
        _revalidate_pending_review(decision, archive_path, record_dir, allowlist_source)

    try:
        return store.stage(evidence, pending_bytes, revalidate_input=revalidate_input)
    except StagingError as exc:
        raise ReviewBlocked(str(exc)) from None


def _revalidate_pending_review(decision: PendingReviewDecision, archive_path: Path,
                               record_dir: Path, source: AllowlistSource | None
                               ) -> observation.VerifiedObservation:
    if (not isinstance(decision, PendingReviewDecision)
            or not isinstance(decision.evidence, observation.VerifiedObservation)
            or any(not isinstance(value, str) for value in (
                decision.local_evidence_id, decision.reviewer_sid, decision.review_result,
                decision.decision_reason, decision.reviewed_at_utc, decision.publish_authorization,
            ))
            or decision.publish_authorization != "NONE"
            or decision.review_result not in ("ACCEPTED", "HOLD", "REJECTED")
            or len(decision.decision_reason) > 500
            or (decision.review_result != "ACCEPTED" and not decision.decision_reason.strip())):
        raise ReviewBlocked("invalid pending review; HOLD")
    try:
        current = observation._load_verified_observation_snapshot(archive_path, record_dir)
        reviewed_at = observation._timestamp(decision.reviewed_at_utc)
        if (current != decision.evidence
                or decision.local_evidence_id != current.record["evidence_id"]
                or reviewed_at < observation._timestamp(current.record["record_created_at_utc"])
                or _review_clock() < reviewed_at):
            raise ReviewBlocked("reviewed snapshot or clock changed; HOLD")
    except (ObservationError, A1InspectionError, OSError):
        raise ReviewBlocked("input snapshot revalidation failed; HOLD") from None
    sid = require_process_sid()
    try:
        require_authorized_sid(sid, source)
    except AllowlistError:
        raise ReviewBlocked("reviewer authorization revalidation failed; HOLD") from None
    if sid != decision.reviewer_sid:
        raise ReviewBlocked("reviewer identity changed; HOLD")
    return current
