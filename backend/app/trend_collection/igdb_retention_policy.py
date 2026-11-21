"""IGDB retention assessment only. No database reads, writes or publication rights.

Thirty days is a proposed *upper bound*, not a granted usage licence.
Callers must separately verify IGDB/Twitch permissions and any shorter limits.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256

MAX_PROPOSED_DAYS = 30
IGDB_IDENTITY = re.compile(r"igdb-game:([1-9][0-9]{0,19})\Z")
IGDB_URL = re.compile(r"https://www\.igdb\.com/games/[a-z0-9][a-z0-9-]{0,254}\Z")


class RetentionReviewError(ValueError):
    """Only bounded codes; never expose data supplied by a source."""


@dataclass(frozen=True, slots=True)
class StoredSourceEvidence:
    """Minimal evidence assembled by a future privileged, read-only auditor."""

    source_id: int
    trend_id: int
    platform: str
    external_id: str
    source_key: str
    source_url: str
    collected_at: datetime


@dataclass(frozen=True, slots=True)
class ExpiryReview:
    source_id: int
    trend_id: int
    expires_at_utc: datetime
    due_for_review: bool


def _as_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise RetentionReviewError("NAIVE_OR_INVALID_TIMESTAMP")
    return value.astimezone(timezone.utc)


def assess_igdb_expiry(
    row: StoredSourceEvidence,
    now: datetime,
    *,
    retention_days: int = MAX_PROPOSED_DAYS,
) -> ExpiryReview:
    """Calculate a proposed purge deadline; never recommend direct parent DELETE."""
    if type(row) is not StoredSourceEvidence:
        raise RetentionReviewError("INVALID_RECORD")
    if type(retention_days) is not int or not 1 <= retention_days <= 30:
        raise RetentionReviewError("INVALID_RETENTION_LIMIT")
    if (type(row.source_id) is not int or row.source_id <= 0
            or type(row.trend_id) is not int or row.trend_id <= 0
            or row.platform != "ETC"
            or not isinstance(row.external_id, str)
            or IGDB_IDENTITY.fullmatch(row.external_id) is None
            or not isinstance(row.source_url, str)
            or IGDB_URL.fullmatch(row.source_url) is None
            or not isinstance(row.source_key, str)
            or row.source_key != sha256(
                f"ETC:{row.external_id}".encode("utf-8")
            ).hexdigest()):
        raise RetentionReviewError("SOURCE_IDENTITY_UNVERIFIED")
    collected = _as_utc(row.collected_at)
    current = _as_utc(now)
    if collected > current:
        raise RetentionReviewError("FUTURE_COLLECTION_TIMESTAMP")
    expiration = collected + timedelta(days=retention_days)
    return ExpiryReview(
        source_id=row.source_id,
        trend_id=row.trend_id,
        expires_at_utc=expiration,
        due_for_review=current >= expiration,
    )
