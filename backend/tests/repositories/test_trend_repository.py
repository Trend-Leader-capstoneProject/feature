from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.db_enums import TrendStatus
from app.models.trend import Trend
from app.models.trend_category_map import TrendCategoryMap
from app.repositories.trend_repository import TrendRepository

pytestmark = pytest.mark.integration


def create_test_trend(
    db_session: Session,
    *,
    normalized_title: str,
    collected_at: datetime,
    status: TrendStatus = TrendStatus.ACTIVE,
) -> Trend:
    """TrendRepository 통합 테스트용 Trend를 생성한다."""

    trend = Trend(
        title=normalized_title,
        normalized_title=normalized_title,
        summary=None,
        thumbnail_url=None,
        status=status,
        first_collected_at=collected_at,
        last_collected_at=collected_at,
        updated_at=None,
    )

    db_session.add(
        trend,
    )
    db_session.flush()

    return trend


def create_test_category(
    db_session: Session,
    *,
    category_name: str,
) -> Category:
    """TrendRepository 필터 테스트용 Category를 생성한다."""

    category = Category(
        category_code=None,
        category_name=category_name,
        sort_order=1,
        is_active=True,
        parent_id=None,
    )

    db_session.add(
        category,
    )
    db_session.flush()

    return category

def link_trend_category(
    db_session: Session,
    *,
    trend: Trend,
    category: Category,
) -> TrendCategoryMap:
    """테스트 Trend와 Category를 연결한다."""

    link = TrendCategoryMap(
        trend_id=trend.trend_id,
        category_id=category.category_id,
        is_primary=False,
    )

    db_session.add(
        link,
    )
    db_session.flush()

    return link


def test_find_page_returns_only_active_trends_in_latest_order(
    db_session: Session,
) -> None:
    """ACTIVE Trend만 last_collected_at 내림차순으로 조회한다."""

    oldest = create_test_trend(
        db_session,
        normalized_title=(
            "trend-repository-active-oldest"
        ),
        collected_at=datetime(
            2026,
            9,
            28,
            10,
            0,
            0,
        )
    )
    newest = create_test_trend(
        db_session,
        normalized_title=(
            "trend-repository-active-newest"
        ),
        collected_at=datetime(
            2026,
            9,
            28,
            12,
            0,
            0,
        ),
    )
    middle = create_test_trend(
        db_session,
        normalized_title=(
            "trend-repository-active-middle"
        ),
        collected_at=datetime(
            2026,
            9,
            28,
            11,
            0,
            0,
        ),
    )
    hidden = create_test_trend(
        db_session,
        normalized_title=(
            "trend-repository-hidden-newest"
        ),
        collected_at=datetime(
            2026,
            9,
            28,
            13,
            0,
            0,
        ),
        status=TrendStatus.HIDDEN,
    )

    repository = TrendRepository(
        db=db_session,
    )

    result = repository.find_page(
        limit=20,
        category_ids=None,
        cursor_last_collected_at=None,
        cursor_trend_id=None,
    )

    result_ids = [
        trend.trend_id
        for trend in result
    ]

    assert result_ids == [
        newest.trend_id,
        middle.trend_id,
        oldest.trend_id,
    ]

def test_find_page_uses_trend_id_as_timestamp_tie_breaker(
    db_session: Session,
) -> None:
    """수집 시각이 같으면 trend_id가 큰 Trend를 먼저 반환한다."""

    collected_at = datetime(
        2026,
        9,
        28,
        12,
        0,
        0,
    )
    lower_id = create_test_trend(
        db_session,
        normalized_title=(
            "trend-repository-tie-lower"
        ),
        collected_at=collected_at,
    )
    higher_id = create_test_trend(
        db_session,
        normalized_title=(
            "trend-repository-tie-higher"
        ),
        collected_at=collected_at,
    )

    assert (
        higher_id.trend_id
        > lower_id.trend_id
    )

    repository = TrendRepository(
        db=db_session,
    )

    result = repository.find_page(
        limit=20,
        category_ids=None,
        cursor_last_collected_at=None,
        cursor_trend_id=None,
    )

    assert [
        trend.trend_id
        for trend in result
    ] == [
        higher_id.trend_id,
        lower_id.trend_id,
    ]
