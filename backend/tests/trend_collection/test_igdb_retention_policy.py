"""Pure IGDB retention audit tests: neither a purge job nor licence clearance."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from app.trend_collection.igdb_retention_policy import (
    MAX_PROPOSED_DAYS,
    RetentionReviewError,
    StoredSourceEvidence,
    assess_igdb_expiry,
)

NOW = datetime(2026, 11, 21, 2, tzinfo=timezone.utc)
EXTERNAL_ID = "igdb-game:87622"


def source(*, collected_at=None):
    return StoredSourceEvidence(
        source_id=101,
        trend_id=201,
        platform="ETC",
        external_id=EXTERNAL_ID,
        source_key=sha256(f"ETC:{EXTERNAL_ID}".encode()).hexdigest(),
        source_url="https://www.igdb.com/games/free-fire",
        collected_at=(NOW - timedelta(days=29) if collected_at is None
                      else collected_at),
    )


def test_proposed_default_is_only_an_upper_bound():
    assert MAX_PROPOSED_DAYS == 30
    review = assess_igdb_expiry(source(), NOW)
    assert review.due_for_review is False
    assert review.expires_at_utc == NOW + timedelta(days=1)
    assert not hasattr(review, "delete")


@pytest.mark.parametrize("age,expected", [(0, False), (29, False),
                                           (30, True), (31, True)])
def test_30_day_boundary(age, expected):
    row = source(collected_at=NOW - timedelta(days=age))
    assert assess_igdb_expiry(row, NOW).due_for_review is expected


def test_shorter_retention_restriction_can_be_enforced():
    row = source(collected_at=NOW - timedelta(hours=25))
    assert assess_igdb_expiry(row, NOW, retention_days=1).due_for_review
    assert not assess_igdb_expiry(row, NOW, retention_days=30).due_for_review


@pytest.mark.parametrize("value", [0, -1, 31, True, None, 1.5, "30"])
def test_no_retention_policy_above_30_days(value):
    with pytest.raises(RetentionReviewError, match="INVALID_RETENTION_LIMIT"):
        assess_igdb_expiry(source(), NOW, retention_days=value)


@pytest.mark.parametrize("changes", [
    {"platform": "GITHUB"},
    {"external_id": "github-release:123"},
    {"external_id": "igdb-game:0"},
    {"external_id": "igdb-game:0001"},
    {"source_key": "0" * 64},
    {"source_url": "https://evil.test/games/free-fire"},
    {"source_id": True},
    {"trend_id": -1},
])
def test_unrelated_or_forged_source_rejected(changes):
    with pytest.raises(RetentionReviewError, match="SOURCE_IDENTITY_UNVERIFIED"):
        assess_igdb_expiry(replace(source(), **changes), NOW)


def test_reject_naive_and_future_timestamps():
    with pytest.raises(RetentionReviewError, match="NAIVE_OR_INVALID_TIMESTAMP"):
        assess_igdb_expiry(source(collected_at=datetime(2026, 11, 1)), NOW)
    with pytest.raises(RetentionReviewError, match="NAIVE_OR_INVALID_TIMESTAMP"):
        assess_igdb_expiry(source(), NOW.replace(tzinfo=None))
    with pytest.raises(RetentionReviewError, match="FUTURE_COLLECTION_TIMESTAMP"):
        assess_igdb_expiry(source(collected_at=NOW + timedelta(seconds=1)), NOW)


def test_timezone_conversion_is_utc_based():
    kst = timezone(timedelta(hours=9))
    row = source(collected_at=(NOW - timedelta(days=30)).astimezone(kst))
    assert assess_igdb_expiry(row, NOW).due_for_review is True
