from datetime import UTC, datetime

from app.models.category import Category
from app.models.trend import Trend
from app.models.trend_source import TrendSource
from app.schemas.trend_schema import (
    TrendCategoryItem,
    TrendCategoryParent,
    TrendLatestSource,
    TrendListItem,
)


def build_trend_list_item(
    *,
    trend: Trend,
    latest_source: TrendSource | None,
    category_pairs: list[
        tuple[Category, Category]
    ],
) -> TrendListItem:
    """Trend ORM 조회 결과를 공통 목록 응답 항목으로 조립한다."""

    categories = _build_categories(
        category_pairs,
    )

    source = None

    if latest_source is not None:
        source = TrendLatestSource(
            source_id=latest_source.source_id,
            platform=latest_source.platform,
            source_title=latest_source.source_title,
            source_url=latest_source.source_url,
        )

    return TrendListItem(
        trend_id=trend.trend_id,
        title=trend.title,
        summary=trend.summary,
        thumbnail_url=trend.thumbnail_url,
        last_collected_at=_as_utc_datetime(
            trend.last_collected_at,
        ),
        categories=categories,
        latest_source=source,
    )


def _build_categories(
    category_pairs: list[
        tuple[Category, Category]
    ],
) -> list[TrendCategoryItem]:
    """Category 중복을 제거하고 결정적인 순서로 응답을 구성한다."""

    unique_pairs: dict[
        int,
        tuple[Category, Category],
    ] = {}

    for child, parent in category_pairs:
        unique_pairs.setdefault(
            child.category_id,
            (
                child,
                parent,
            ),
        )

    ordered_pairs = sorted(
        unique_pairs.values(),
        key=lambda pair: (
            pair[1].sort_order,
            pair[1].category_id,
            pair[0].sort_order,
            pair[0].category_id,
        ),
    )

    return [
        TrendCategoryItem(
            category_id=child.category_id,
            category_name=child.category_name,
            parent=TrendCategoryParent(
                category_id=parent.category_id,
                category_code=parent.category_code,
                category_name=parent.category_name,
            ),
        )
        for child, parent in ordered_pairs
    ]


def _as_utc_datetime(
    value: datetime,
) -> datetime:
    """UTC 저장 시각을 API용 UTC-aware datetime으로 변환한다."""

    if value.tzinfo is None:
        return value.replace(
            tzinfo=UTC,
        )

    return value.astimezone(
        UTC,
    )
