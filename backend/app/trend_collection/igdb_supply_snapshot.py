"""Independently verified IGDB projection without approval authority."""

from datetime import datetime, timezone
from hashlib import sha256

from app.trend_collection.igdb_adapter import (
    DIVERSITY_SCOPE,
    SCOPE,
    SOURCE_ID,
    VISITS_ID,
    IgdbBlocked,
    IgdbReviewAdapter,
    Query,
)
from app.trend_collection.publication_policy import (
    POLICY_VERSION,
    PROFILE,
    PopularitySnapshot,
    _digest,
)

UNBOUND = "UNBOUND_OPERATIONAL"


def project_verified_popularity(
    verified: dict, *, diversity=False,
) -> PopularitySnapshot:
    """Call only on IgdbReviewAdapter.verify_review's rebuilt output.

    This is a value projection, not proof of rights or authorization.
    """
    if type(verified) is not dict or verified.get("source_id") != SOURCE_ID:
        raise IgdbBlocked("INVALID_VERIFIED_PREVIEW")
    scope = DIVERSITY_SCOPE if diversity else SCOPE
    if (verified.get("scope") != scope
            or verified.get("publication_status") != "NOT_FOR_PUBLICATION"
            or verified.get("publish_authorization") != "NONE"):
        raise IgdbBlocked("INVALID_VERIFIED_PREVIEW")
    identity = verified["candidate_identity"]
    category = verified["proposed_category_ref"]
    source = verified["proposed_source"]
    if not isinstance(identity, str) or not identity.startswith("igdb-game:"):
        raise IgdbBlocked("INVALID_VERIFIED_PREVIEW")
    if (source["external_id"] != identity or source["platform"] != "ETC"
            or source["source_url"] is None):
        raise IgdbBlocked("INVALID_VERIFIED_PREVIEW")
    return PopularitySnapshot(
        profile_id=PROFILE,
        policy_version=POLICY_VERSION,
        target=UNBOUND,
        candidate_identity=identity,
        evidence_ref=_digest({
            "scope": scope,
            "candidate_identity": identity,
            "evidence_digest": verified["evidence_digest"],
            "calculated_at": verified["calculated_at"],
        }),
        title=verified["title"],
        normalized_title=verified["normalized_title"],
        summary=verified["summary"],
        source_url=source["source_url"],
        external_id=identity,
        source_key=sha256(f"ETC:{identity}".encode()).hexdigest(),
        platform="ETC",
        parent_code=category["parent_code"],
        child_name=category["child_name"],
        observed_at_utc=verified["observed_at_utc"],
        calculated_at_utc=verified["calculated_at"],
        rank=verified["rank"],
        metric_id=VISITS_ID,
        proposed_status="ACTIVE",
    )


class IgdbSnapshotBridge:
    """Explicit projection bridge; caller must enforce operational approval."""

    scope = SCOPE

    def __init__(self, query: Query, *, diversity=False):
        self._review = IgdbReviewAdapter(query, diversity=diversity)
        self._diversity = diversity
        self.scope = self._review.scope

    @property
    def diagnostics(self):
        return self._review.diagnostics

    def collect_preview(self, *, after_game_id=None):
        return self._review.collect_review(
            datetime.now(timezone.utc), after_game_id=after_game_id,
        )

    def verify(self, preview, now: datetime) -> PopularitySnapshot:
        verified = self._review.verify_review(preview, now)
        return project_verified_popularity(verified, diversity=self._diversity)
