from datetime import datetime

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.db_enums import (
    CategoryCode,
    TrendSourcePlatform,
    TrendStatus,
)
from app.models.trend import Trend
from app.models.trend_category_map import TrendCategoryMap
from app.models.trend_source import TrendSource
from app.repositories.trend_repository import TrendRepository

pytestmark = pytest.mark.integration

def create_test_trend(
    db_session: Session,
    *,
    normalized_title: str,
) -> Trend:
    """Batch 조회 테스트용 Trend를 생성한다."""

    collected_at = datetime(
        2026,
        9,
        29,
        12,
        0,
        0,
    )

    trend = Trend(
        title=normalized_title,
        normalized_title=normalized_title,
        summary=None,
        thumbnail_url=None,
        status=TrendStatus.ACTIVE,
        first_collected_at=collected_at,
        last_collected_at=collected_at,
        updated_at=None,
    )

    db_session.add(
        trend,
    )
    db_session.flush()

    return trend


def create_test_source(
    db_session: Session,
    *,
    trend: Trend,
    source_key: str,
    source_title: str | None,
    collected_at: datetime,
) -> TrendSource:
    """Batch 조회 테스트용 Trend Source를 생성한다."""

    source = TrendSource(
        source_key=source_key,
        source_url=(
            f"https://example.com/{source_key}"
        ),
        source_title=source_title,
        platform=TrendSourcePlatform.ETC,
        collected_at=collected_at,
        external_id=None,
        trend_id=trend.trend_id,
    )

    db_session.add(
        source,
    )
    db_session.flush()

    return source

def test_find_latest_sources_returns_latest_source_per_trend(
    db_session: Session,
) -> None:
    """각 Trend의 collected_at이 가장 최근인 Source를 반환한다."""

    first_trend = create_test_trend(
        db_session,
        normalized_title=(
            "trend-batch-source-first"
        ),
    )
    second_trend = create_test_trend(
        db_session,
        normalized_title=(
            "trend-batch-source-second"
        )
    )

    first_old = create_test_source(
        db_session,
        trend=first_trend,
        source_key="source-first-old",
        source_title="첫 번째 오래된 Source",
        collected_at=datetime(
            2026,
            9,
            29,
            10,
            0,
            0,
        ),
    )
    first_latest = create_test_source(
        db_session,
        trend=first_trend,
        source_key="source-first-latest",
        source_title="첫 번째 최신 Source",
        collected_at=datetime(
            2026,
            9,
            29,
            12,
            0,
            0,
        ),
    )
    second_latest = create_test_source(
        db_session,
        trend=second_trend,
        source_key="source-second-latest",
        source_title="두 번째 최신 Source",
        collected_at=datetime(
            2026,
            9,
            29,
            11,
            0,
            0,
        ),
    )

    repository = TrendRepository(
        db=db_session,
    )

    result = (
        repository
        .find_latest_sources_by_trend_ids(
            [
                first_trend.trend_id,
                second_trend.trend_id,
            ]
        )
    )

    assert {
        trend_id: source.source_id
        for trend_id, source in result.items()
    } == {
        first_trend.trend_id: (
            first_latest.source_id
        ),
        second_trend.trend_id: (
            second_latest.source_id
        ),
    }

    assert (
        result[first_trend.trend_id].source_id
        != first_old.source_id
    )

def create_test_category(
    db_session: Session,
    *,
    category_name: str,
    category_code: CategoryCode | None = None,
    parent_id: int | None = None,
    is_active: bool = True,
    sort_order: int = 1,
) -> Category:
    """Batch 조회 테스트용 Category를 생성한다."""

    category = Category(
        category_code=category_code,
        category_name=category_name,
        sort_order=sort_order,
        is_active=is_active,
        parent_id=parent_id,
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
    """Batch 조회 테스트용 Trend-Category 연결을 생성한다."""

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


def test_find_latest_sources_uses_source_id_as_tie_breaker(
    db_session: Session,
) -> None:
    """collected_at 동률이면 source_id가 큰 Source를 선택한다."""

    trend = create_test_trend(
        db_session,
        normalized_title=(
            "trend-batch-source-tie"
        ),
    )

    collected_at = datetime(
        2026,
        9,
        29,
        12,
        0,
        0,
    )

    lower_id = create_test_source(
        db_session,
        trend=trend,
        source_key="source-tie-lower",
        source_title="낮은 Source ID",
        collected_at=collected_at,
    )
    higher_id = create_test_source(
        db_session,
        trend=trend,
        source_key="source-tie-higher",
        source_title="높은 Source ID",
        collected_at=collected_at,
    )

    assert (
        higher_id.source_id
        > lower_id.source_id
    )

    repository = TrendRepository(
        db=db_session,
    )

    result = (
        repository
        .find_latest_sources_by_trend_ids(
            [
                trend.trend_id,
            ]
        )
    )

    assert (
        result[trend.trend_id].source_id
        == higher_id.source_id
    )


def test_find_latest_sources_omits_trend_without_source(
    db_session: Session,
) -> None:
    """Source가 없는 Trend는 결과 dict에 포함하지 않는다."""

    with_source = create_test_trend(
        db_session,
        normalized_title=(
            "trend-batch-with-source"
        ),
    )
    without_source = create_test_trend(
        db_session,
        normalized_title=(
            "trend-batch-without-source"
        ),
    )

    source = create_test_source(
        db_session,
        trend=with_source,
        source_key="source-existing",
        source_title=None,
        collected_at=datetime(
            2026,
            9,
            29,
            12,
            0,
            0,
        ),
    )

    repository = TrendRepository(
        db=db_session,
    )

    result = (
        repository
        .find_latest_sources_by_trend_ids(
            [
                with_source.trend_id,
                without_source.trend_id,
            ]
        )
    )

    assert (
        result[with_source.trend_id].source_id
        == source.source_id
    )
    assert (
        without_source.trend_id
        not in result
    )


def test_find_latest_sources_only_returns_requested_trends(
    db_session: Session,
) -> None:
    """요청하지 않은 Trend의 Source는 Batch 결과에서 제외한다."""

    requested = create_test_trend(
        db_session,
        normalized_title=(
            "trend-batch-source-requested"
        ),
    )
    unrelated = create_test_trend(
        db_session,
        normalized_title=(
            "trend-batch-source-unrelated"
        ),
    )

    requested_source = create_test_source(
        db_session,
        trend=requested,
        source_key="source-requested",
        source_title="요청 Source",
        collected_at=datetime(
            2026,
            9,
            29,
            12,
            0,
            0,
        ),
    )
    create_test_source(
        db_session,
        trend=unrelated,
        source_key="source-unrelated",
        source_title="무관 Source",
        collected_at=datetime(
            2026,
            9,
            29,
            13,
            0,
            0,
        ),
    )

    repository = TrendRepository(
        db=db_session,
    )

    result = (
        repository
        .find_latest_sources_by_trend_ids(
            [
                requested.trend_id,
            ]
        )
    )

    assert list(result) == [
        requested.trend_id,
    ]
    assert (
        result[requested.trend_id].source_id
        == requested_source.source_id
    )


def test_find_latest_sources_returns_empty_dict_for_empty_ids(
    db_session: Session,
) -> None:
    """Trend ID가 없으면 빈 결과를 반환한다."""

    repository = TrendRepository(
        db=db_session,
    )

    result = (
        repository
        .find_latest_sources_by_trend_ids(
            []
        )
    )

    assert result == {}


def test_find_categories_groups_all_mappings_by_requested_trend(
    db_session: Session,
) -> None:
    """요청 Trend별 모든 Category와 Parent를 일괄 반환한다."""

    parent = create_test_category(
        db_session,
        category_name="Batch Parent",
        category_code=CategoryCode.GAME,
        is_active=False,
        sort_order=1,
    )

    first_child = create_test_category(
        db_session,
        category_name="Batch Child A",
        parent_id=parent.category_id,
        is_active=True,
        sort_order=1,
    )
    second_child = create_test_category(
        db_session,
        category_name="Batch Child B",
        parent_id=parent.category_id,
        is_active=False,
        sort_order=2,
    )

    first_trend = create_test_trend(
        db_session,
        normalized_title=(
            "trend-batch-category-first"
        ),
    )
    second_trend = create_test_trend(
        db_session,
        normalized_title=(
            "trend-batch-category-second"
        ),
    )
    unrelated_trend = create_test_trend(
        db_session,
        normalized_title=(
            "trend-batch-category-unrelated"
        ),
    )

    link_trend_category(
        db_session,
        trend=first_trend,
        category=first_child,
    )
    link_trend_category(
        db_session,
        trend=first_trend,
        category=second_child,
    )
    link_trend_category(
        db_session,
        trend=second_trend,
        category=second_child,
    )
    link_trend_category(
        db_session,
        trend=unrelated_trend,
        category=first_child,
    )

    repository = TrendRepository(
        db=db_session,
    )

    result = (
        repository
        .find_categories_by_trend_ids(
            [
                first_trend.trend_id,
                second_trend.trend_id,
            ]
        )
    )

    assert set(result) == {
        first_trend.trend_id,
        second_trend.trend_id,
    }

    assert {
        (
            child.category_id,
            parent_category.category_id,
        )
        for child, parent_category
        in result[first_trend.trend_id]
    } == {
        (
            first_child.category_id,
            parent.category_id,
        ),
        (
            second_child.category_id,
            parent.category_id,
        ),
    }

    assert {
        (
            child.category_id,
            parent_category.category_id,
        )
        for child, parent_category
        in result[second_trend.trend_id]
    } == {
        (
            second_child.category_id,
            parent.category_id,
        ),
    }


def test_find_categories_returns_empty_dict_for_empty_ids(
    db_session: Session,
) -> None:
    """Trend ID가 없으면 Category Batch 조회를 생략한다."""

    repository = TrendRepository(
        db=db_session,
    )

    result = (
        repository
        .find_categories_by_trend_ids(
            []
        )
    )

    assert result == {}

def test_find_latest_sources_uses_single_query_for_multiple_trends(
    db_session: Session,
) -> None:
    """여러 Trend의 최신 Source를 단일 Query로 조회한다."""

    trends = [
        create_test_trend(
            db_session,
            normalized_title=(
                f"trend-batch-source-query-{index}"
            ),
        )
        for index in range(3)
    ]

    for index, trend in enumerate(
        trends,
        start=1,
    ):
        create_test_source(
            db_session,
            trend=trend,
            source_key=(
                f"source-query-{index}"
            ),
            source_title=(
                f"Source Query {index}"
            ),
            collected_at=datetime(
                2026,
                9,
                29,
                12,
                index,
                0,
            ),
        )

    repository = TrendRepository(
        db=db_session,
    )

    statements: list[str] = []

    def record_statement(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        statements.append(
            statement,
        )

    bind = db_session.get_bind()

    event.listen(
        bind,
        "before_cursor_execute",
        record_statement,
    )

    try:
        result = (
            repository
            .find_latest_sources_by_trend_ids(
                [
                    trend.trend_id
                    for trend in trends
                ]
            )
        )
    finally:
        event.remove(
            bind,
            "before_cursor_execute",
            record_statement,
        )

    assert len(result) == 3
    assert len(statements) == 1

def test_find_categories_uses_single_query_for_multiple_trends(
    db_session: Session,
) -> None:
    """여러 Trend의 Category와 Parent를 단일 Query로 조회한다."""

    parent = create_test_category(
        db_session,
        category_name=(
            "Batch Query Parent"
        ),
        category_code=CategoryCode.GAME,
    )

    child = create_test_category(
        db_session,
        category_name=(
            "Batch Query Child"
        ),
        parent_id=parent.category_id,
    )

    trends = [
        create_test_trend(
            db_session,
            normalized_title=(
                f"trend-batch-category-query-{index}"
            ),
        )
        for index in range(3)
    ]

    for trend in trends:
        link_trend_category(
            db_session,
            trend=trend,
            category=child,
        )

    repository = TrendRepository(
        db=db_session,
    )

    statements: list[str] = []

    def record_statement(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        statements.append(
            statement,
        )

    bind = db_session.get_bind()

    event.listen(
        bind,
        "before_cursor_execute",
        record_statement,
    )

    try:
        result = (
            repository
            .find_categories_by_trend_ids(
                [
                    trend.trend_id
                    for trend in trends
                ]
            )
        )
    finally:
        event.remove(
            bind,
            "before_cursor_execute",
            record_statement,
        )

    assert len(result) == 3
    assert len(statements) == 1
