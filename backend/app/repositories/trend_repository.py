from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    and_,
    exists,
    or_,
    select,
)
from sqlalchemy.orm import Session

from app.models.db_enums import TrendStatus
from app.models.trend import Trend
from app.models.trend_category_map import TrendCategoryMap


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
