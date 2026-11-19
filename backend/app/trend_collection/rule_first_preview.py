"""Rule-first release preview; no AI, network, database or publication authority."""

from datetime import datetime, timezone

from app.trend_collection.godot_release_collector import (
    REPO,
    TAG,
    CollectionError,
    ReleaseEvidence,
    build_candidate,
)


def build_rule_first_preview(evidence: ReleaseEvidence, observed_at: datetime):
    """Check metadata consistency, not independent provenance or source rights."""
    if (
        type(evidence) is not ReleaseEvidence
        or type(evidence.release_id) is not int
        or not 1 <= evidence.release_id < 10**20
        or not isinstance(evidence.tag, str)
        or not TAG.fullmatch(evidence.tag)
        or type(evidence.prerelease) is not bool
        or evidence.prerelease == evidence.tag.endswith("-stable")
        or evidence.url != f"https://github.com/{REPO}/releases/tag/{evidence.tag}"
    ):
        raise CollectionError("RULE_METADATA_MISMATCH")
    if any(
        not isinstance(value, datetime) or value.utcoffset() is None
        for value in (evidence.published_at, observed_at)
    ):
        raise CollectionError("RULE_TIMEZONE_REQUIRED")
    candidate = build_candidate(evidence, observed_at.astimezone(timezone.utc))
    version, kind = evidence.tag.split("-", 1)
    label = "정식" if kind == "stable" else kind
    candidate.update(
        summary=f"Godot {version} {label} 버전이 공개되었습니다.",
        analysis_status="RULE_BASED_PREVIEW",
        analysis_method="FIXED_RELEASE_TEMPLATE",
        ai_api_calls=0,
        source_rights_verified=False,
    )
    return candidate
