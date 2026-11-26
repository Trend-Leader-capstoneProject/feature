from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Callable

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
from app.models.db_enums import TrendSourcePlatform, TrendStatus
from app.models.trend import Trend
from app.models.trend_category_map import TrendCategoryMap
from app.models.trend_related_article import TrendRelatedArticle
from app.models.trend_source import TrendSource
from app.trend_collection.igdb_retention_policy import MAX_POLICY_DAYS
from app.trend_collection.searchapi_interest import (
    SOURCE_URL as INTEREST_SOURCE_URL,
    WINDOW as INTEREST_WINDOW,
)
from app.trend_collection.searchapi_related_articles import WINDOW as ARTICLE_WINDOW


class TrendRepository:
    """전체 Trend 목록 조회를 위한 데이터 접근을 담당한다."""

    def __init__(
        self,
        db: Session,
        *,
        utc_now: Callable[[], datetime] | None = None,
    ) -> None:
        self.db = db
        self._utc_now = utc_now or (lambda: datetime.now(UTC))

    def _visibility_now(self) -> datetime:
        """The storage contract uses UTC timestamps without tzinfo in MariaDB."""
        now = self._utc_now()
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ValueError("IGDB_VISIBILITY_CLOCK_INVALID")
        return now.astimezone(UTC).replace(tzinfo=None)

    @staticmethod
    def _expired_igdb_source(cutoff: datetime):
        # ETC also contains non-IGDB sources: only the fixed ID namespace
        # identifies IGDB. Fail closed for expired mixed-source trends.
        return and_(
            TrendSource.platform == TrendSourcePlatform.ETC,
            TrendSource.external_id.is_not(None),
            TrendSource.external_id.startswith("igdb-game:"),
            TrendSource.collected_at <= cutoff,
        )

    def _expired_source(self, now: datetime | None = None):
        if now is None:
            now = self._visibility_now()
        return or_(
            self._expired_igdb_source(now - timedelta(days=MAX_POLICY_DAYS)),
            and_(
                TrendSource.platform == TrendSourcePlatform.ETC,
                TrendSource.external_id.is_not(None),
                TrendSource.external_id.startswith("searchapi-interest:"),
                TrendSource.collected_at <= now - timedelta(hours=24),
            ),
        )

    def find_page(
        self,
        *,
        limit: int,
        category_ids: list[int] | None,
        cursor_last_collected_at: datetime | None,
        cursor_trend_id: int | None,
    ) -> list[Trend]:
        """정렬·Category·Cursor 조건을 적용한 Trend Page를 조회한다."""

        expired_source = exists(
            select(1).select_from(TrendSource).where(
                TrendSource.trend_id == Trend.trend_id,
                self._expired_source(),
            )
        )
        statement = select(
            Trend,
        ).where(
            Trend.status == TrendStatus.ACTIVE,
            ~expired_source,
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
                TrendSource.trend_id.in_(trend_ids),
                ~self._expired_source(),
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


    def find_related_articles_by_trend_ids(
        self, trend_ids: list[int],
    ) -> dict[int, list[TrendRelatedArticle]]:
        """Batch read only currently visible reference links."""
        if not trend_ids:
            return {}
        now = self._visibility_now()
        # Reference links belong to the exact stored interest observation.
        # They must not extend visibility or leak through an unrelated source.
        article = TrendRelatedArticle
        valid_observation = exists(
            select(1).select_from(TrendSource).where(
                TrendSource.trend_id == article.trend_id,
                TrendSource.platform == TrendSourcePlatform.ETC,
                TrendSource.external_id.startswith("searchapi-interest:"),
                TrendSource.source_url == INTEREST_SOURCE_URL,
                TrendSource.collected_at == article.collected_at,
                TrendSource.collected_at > now - INTEREST_WINDOW,
                TrendSource.collected_at <= now,
            )
        )
        expired_source = exists(
            select(1).select_from(TrendSource).where(
                TrendSource.trend_id == Trend.trend_id,
                self._expired_source(now),
            )
        )
        statement = (
            select(article)
            .join(Trend, Trend.trend_id == article.trend_id)
            .where(
                article.trend_id.in_(trend_ids),
                Trend.status == TrendStatus.ACTIVE,
                valid_observation,
                ~expired_source,
                article.published_at > now - ARTICLE_WINDOW,
                article.published_at <= article.collected_at,
                article.collected_at <= now,
                article.selection_order.in_((1, 2)),
            )
            .order_by(article.trend_id, article.selection_order)
        )
        result: dict[int, list[TrendRelatedArticle]] = {}
        for row in self.db.scalars(statement).all():
            group = result.setdefault(row.trend_id, [])
            if len(group) < 2:
                group.append(row)
        return result

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
