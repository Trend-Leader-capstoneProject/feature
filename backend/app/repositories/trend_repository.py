from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    and_,
    exists,
    func,
    or_,
    select,
)
from sqlalchemy.orm import (
    Session,
    aliased,
)

from app.models.category import Category
from app.models.db_enums import TrendStatus
from app.models.trend import Trend
from app.models.trend_category_map import TrendCategoryMap
from app.models.trend_source import TrendSource


class TrendRepository:
    """전체 Trend 목록 조회를 위한 데이터 접근을 담당한다."""

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def find_page(
        self,
        *,
        limit: int,
        category_ids: list[int] | None,
        cursor_last_collected_at: datetime | None,
        cursor_trend_id: int | None,
    ) -> list[Trend]:
        """정렬·Category·Cursor 조건을 적용한 Trend Page를 조회한다."""

        statement = select(
            Trend,
        ).where(
            Trend.status
            == TrendStatus.ACTIVE,
        )

        if category_ids is not None:
            category_match = exists(
                select(
                    1,
                ).select_from(
                    TrendCategoryMap,
                )
                .where(
                    TrendCategoryMap.trend_id
                    == Trend.trend_id,
                    TrendCategoryMap.category_id.in_(
                        category_ids,
                    ),
                )
            )

            statement = statement.where(
                category_match,
            )

        if (
            cursor_last_collected_at
            is not None
            and cursor_trend_id
            is not None
        ):
            statement = statement.where(
                or_(
                    Trend.last_collected_at
                    < cursor_last_collected_at,
                    and_(
                        Trend.last_collected_at
                        == cursor_last_collected_at,
                        Trend.trend_id
                        < cursor_trend_id,
                    ),
                )
            )

        statement = (
            statement
            .order_by(
                Trend.last_collected_at.desc(),
                Trend.trend_id.desc(),
            )
            .limit(
                limit,
            )
        )

        return list(
            self.db.scalars(
                statement,
            ).all()
        )

    def find_latest_sources_by_trend_ids(
        self,
        trend_ids: list[int],
    ) -> dict[int, TrendSource]:
        """Trend별 가장 최근 Source를 한 번의 Batch 조회로 반환한다."""

        if not trend_ids:
            return {}

        ranked_sources = (
            select(
                TrendSource.source_id.label(
                    "source_id",
                ),
                TrendSource.trend_id.label(
                    "trend_id",
                ),
                func.row_number()
                .over(
                    partition_by=(
                        TrendSource.trend_id
                    ),
                    order_by=(
                        TrendSource.collected_at.desc(),
                        TrendSource.source_id.desc(),
                    ),
                )
                .label(
                    "row_number",
                ),
            ).where(
                TrendSource.trend_id.in_(
                    trend_ids,
                )
            )
            .subquery()
        )

        statement = (
            select(
                TrendSource,
            )
            .join(
                ranked_sources,
                ranked_sources.c.source_id
                == TrendSource.source_id,
            )
            .where(
                ranked_sources.c.row_number
                == 1,
            )
        )

        sources = list(
            self.db.scalars(
                statement,
            ).all()
        )

        return {
            source.trend_id: source
            for source in sources
        }


    def find_categories_by_trend_ids(
        self,
        trend_ids: list[int],
    ) -> dict[
        int,
        list[
            tuple[
                Category,
                Category,
            ]
        ],
    ]:
        """Trend별 세부분류와 부모 대분류를 한 번에 조회한다."""

        if not trend_ids:
            return {}

        child_category = aliased(
            Category,
        )
        parent_category = aliased(
            Category,
        )

        statement = (
            select(
                TrendCategoryMap.trend_id,
                child_category,
                parent_category,
            )
            .join(
                child_category,
                child_category.category_id
                == TrendCategoryMap.category_id,
            )
            .join(
                parent_category,
                parent_category.category_id
                == child_category.parent_id,
            )
            .where(
                TrendCategoryMap.trend_id.in_(
                    trend_ids,
                )
            )
        )

        rows = self.db.execute(
            statement,
        ).all()

        result: dict[
            int,
            list[
                tuple[
                    Category,
                    Category,
                ]
            ],
        ] = {}

        for (
            trend_id,
            child,
            parent,
        ) in rows:
            result.setdefault(
                trend_id,
                [],
            ).append(
                (
                    child,
                    parent,
                )
            )

        return result
