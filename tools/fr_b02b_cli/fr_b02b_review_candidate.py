"""Phase 4B-1 read-only review candidate; no acceptance or publication."""

from pathlib import Path

from fr_b02b_observation import _load_verified_observation


def review_candidate(archive_path: Path, record_dir: Path) -> dict[str, str]:
    """Project only validated values, retaining local times and HOLD/NONE.

    The record's binding fields were checked against the same A1 archive bytes.
    This neither authenticates an observer nor creates operational evidence.
    """
    record = _load_verified_observation(archive_path, record_dir)
    return {
        "status": "REVIEW_CANDIDATE_HOLD",
        "local_evidence_id": record["evidence_id"],
        **{key: record[key] for key in (
            "trend_ref", "content_ref", "review_evidence_id", "source_url",
            "confirmed_at_utc", "record_created_at_utc",
            "review_result", "publish_authorization",
        )},
    }
