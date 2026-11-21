"""IGDB expiry read guard on the existing MariaDB trend repository.

Integration tests use only the project's separately approved test database.
No operational writer, network client, or purge is invoked here.
"""

from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest
from sqlalchemy.orm import Session

from app.models.db_enums import TrendSourcePlatform, TrendStatus
from app.models.trend import Trend
from app.models.trend_source import TrendSource
from app.repositories.trend_repository import TrendRepository

pytestmark = pytest.mark.integration
NOW = datetime(2026, 11, 21, 12, tzinfo=UTC)
CUTOFF = NOW.replace(tzinfo=None) - timedelta(days=30)


def _trend(db: Session, name: str, collected: datetime) -> Trend:
    item = Trend(
        title=name,
        normalized_title=name,
        status=TrendStatus.ACTIVE,
        first_collected_at=collected,
        last_collected_at=collected,
    )
    db.add(item)
    db.flush()
    return item


def _source(
    db: Session,
    trend: Trend,
    identity: str | None,
    collected: datetime,
    *,
    url: str = "https://www.igdb.com/games/fixture-1",
) -> TrendSource:
    item = TrendSource(
        trend_id=trend.trend_id,
        platform=TrendSourcePlatform.ETC,
        external_id=identity,
        source_key=sha256(f"ETC:{identity}".encode()).hexdigest(),
        source_url=url,
        collected_at=collected,
    )
    db.add(item)
    db.flush()
    return item


def _repository(db: Session) -> TrendRepository:
    return TrendRepository(db, utc_now=lambda: NOW)


def _page(repo: TrendRepository, limit=20) -> list[int]:
    return [
        item.trend_id
        for item in repo.find_page(
            limit=limit,
            category_ids=None,
            cursor_last_collected_at=None,
            cursor_trend_id=None,
        )
    ]


def test_expired_igdb_is_excluded_before_cursor_limit(db_session: Session):
    expired = _trend(db_session, "expiry-igdb-old", NOW.replace(tzinfo=None))
    _source(db_session, expired, "igdb-game:101", CUTOFF)

    recent = _trend(
        db_session, "expiry-igdb-recent",
        NOW.replace(tzinfo=None) - timedelta(minutes=1),
    )
    _source(
        db_session, recent, "igdb-game:102", CUTOFF + timedelta(seconds=1),
    )

    godot = _trend(
        db_session, "expiry-godot",
        NOW.replace(tzinfo=None) - timedelta(minutes=2),
    )
    _source(
        db_session, godot, "github-release:godot:103",
        CUTOFF - timedelta(days=100),
        url="https://github.com/godotengine/godot-builds/releases/tag/4.4",
    )

    page = _page(_repository(db_session), limit=2)
    assert page == [recent.trend_id, godot.trend_id]
    assert expired.trend_id not in page


def test_mixed_source_with_expired_igdb_is_held_without_deleting(
    db_session: Session,
):
    """Shared title provenance is not tracked: fail closed, preserve rows."""
    mixed = _trend(db_session, "expiry-igdb-mixed", NOW.replace(tzinfo=None))
    old = _source(db_session, mixed, "igdb-game:201", CUTOFF)
    live = _source(
        db_session, mixed, "github-release:godot:202",
        NOW.replace(tzinfo=None),
        url="https://github.com/godotengine/godot-builds/releases/tag/4.5",
    )
    assert mixed.trend_id not in _page(_repository(db_session))
    assert db_session.get(Trend, mixed.trend_id) is not None
    assert db_session.get(TrendSource, old.source_id) is not None
    assert db_session.get(TrendSource, live.source_id) is not None


def test_unattributed_legacy_etc_source_stays_visible(db_session: Session):
    old = _trend(db_session, "expiry-legacy-source", NOW.replace(tzinfo=None))
    _source(
        db_session, old, None, CUTOFF - timedelta(days=180),
        url="https://example.org/source",
    )
    assert old.trend_id in _page(_repository(db_session))


def test_naive_clock_is_rejected_before_database_query(db_session: Session):
    repository = TrendRepository(
        db_session,
        utc_now=lambda: datetime(2026, 11, 21, 12),
    )
    with pytest.raises(ValueError, match="IGDB_VISIBILITY_CLOCK_INVALID"):
        _page(repository)


def test_latest_source_does_not_return_expired_igdb(db_session: Session):
    mixed = _trend(db_session, "expiry-mixed-latest", NOW.replace(tzinfo=None))
    _source(db_session, mixed, "igdb-game:301", CUTOFF)
    alternative = _source(
        db_session, mixed, "github-release:godot:302",
        CUTOFF - timedelta(days=60),
        url="https://github.com/godotengine/godot-builds/releases/tag/4.6",
    )
    only_expired = _trend(
        db_session, "expiry-only-old", NOW.replace(tzinfo=None),
    )
    _source(db_session, only_expired, "igdb-game:303", CUTOFF)
    recent = _trend(db_session, "expiry-only-fresh", NOW.replace(tzinfo=None))
    fresh = _source(
        db_session, recent, "igdb-game:304", CUTOFF + timedelta(seconds=1),
    )

    result = _repository(db_session).find_latest_sources_by_trend_ids(
        [mixed.trend_id, only_expired.trend_id, recent.trend_id],
    )
    assert result[mixed.trend_id].source_id == alternative.source_id
    assert only_expired.trend_id not in result
    assert result[recent.trend_id].source_id == fresh.source_id
