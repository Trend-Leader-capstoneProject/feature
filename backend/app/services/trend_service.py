from __future__ import annotations

from datetime import UTC, datetime
from typing import (
    NoReturn,
    Protocol,
)

from app.core.exceptions import (
    BadRequestException,
    NotFoundException,
)
from app.models.category import Category
from app.models.trend import Trend
from app.models.trend_source import TrendSource
from app.repositories.category_repository import (
    CategoryRepository,
)
from app.schemas.trend_schema import (
    TrendCategoryItem,
    TrendCategoryParent,
    TrendLatestSource,
    TrendListData,
    TrendListItem,
)
from app.utils.trend_cursor import (
    TrendCursor,
    TrendCursorError,
    decode_trend_cursor,
    encode_trend_cursor,
)


class TrendRepositoryProtocol(
    Protocol,
):
    """TrendService가 요구하는 Trend 조회 Repository 계약."""

    def find_page(
        self,
        *,
        limit: int,
        category_ids: list[int] | None,
        cursor_last_collected_at: datetime | None,
        cursor_trend_id: int | None,
    ) -> list[Trend]:
        """Cursor 조건으로 Trend Page를 조회한다."""
        ...

    def find_latest_sources_by_trend_ids(
        self,
        trend_ids: list[int],
    ) -> dict[int, TrendSource]:
        """Trend별 최신 Source를 일괄 조회한다."""
        ...

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
        """Trend별 세부분류와 부모 대분류를 일괄 조회한다."""
        ...


class TrendService:
    """전체 Trend 목록 조회 비즈니스 규칙을 담당한다."""

    def __init__(
        self,
        *,
        category_repository: CategoryRepository,
        trend_repository: TrendRepositoryProtocol,
    ) -> None:
        self.category_repository = (
            category_repository
        )
        self.trend_repository = (
            trend_repository
        )

    def list_trends(
        self,
        *,
        category_id: int | None,
        limit: int,
        cursor: str | None,
    ) -> TrendListData:
        """필터와 Cursor를 적용하여 최신 Trend 목록을 조회한다."""

        decoded_cursor = (
            self._decode_and_validate_cursor(
                cursor=cursor,
                category_id=category_id,
            )
        )

        category_ids = (
            self._resolve_filter_category_ids(
                category_id=category_id,
            )
        )

        if category_ids == []:
            return TrendListData(
                items=[],
                next_cursor=None,
                has_next=False,
            )

        page_rows = (
            self.trend_repository.find_page(
                limit=limit + 1,
                category_ids=category_ids,
                cursor_last_collected_at=(
                    decoded_cursor.last_collected_at
                    if decoded_cursor
                    else None
                ),
                cursor_trend_id=(
                    decoded_cursor.trend_id
                    if decoded_cursor
                    else None
                ),
            )
        )

        if not page_rows:
            return TrendListData(
                items=[],
                next_cursor=None,
                has_next=False,
            )

        has_next = (
            len(page_rows)
            > limit
        )

        response_trends = (
            page_rows[:limit]
        )

        trend_ids = [
            trend.trend_id
            for trend in response_trends
        ]

        latest_sources = (
            self.trend_repository
            .find_latest_sources_by_trend_ids(
                trend_ids,
            )
        )

        categories_by_trend_id = (
            self.trend_repository
            .find_categories_by_trend_ids(
                trend_ids,
            )
        )

        items = [
            self._build_item(
                trend=trend,
                latest_source=(
                    latest_sources.get(
                        trend.trend_id,
                    )
                ),
                category_pairs=(
                    categories_by_trend_id.get(
                        trend.trend_id,
                        [],
                    )
                ),
            )
            for trend in response_trends
        ]

        next_cursor = None

        if has_next:
            last_trend = (
                response_trends[-1]
            )

            next_cursor = (
                encode_trend_cursor(
                    TrendCursor(
                        last_collected_at=(
                            last_trend.last_collected_at
                        ),
                        trend_id=(
                            last_trend.trend_id
                        ),
                        category_id=category_id,
                    )
                )
            )

        return TrendListData(
            items=items,
            next_cursor=next_cursor,
            has_next=has_next,
        )

    def _decode_and_validate_cursor(
        self,
        *,
        cursor: str | None,
        category_id: int | None,
    ) -> TrendCursor | None:
        """Cursor 형식과 현재 Category 필터 문맥을 검증한다."""

        if cursor is None:
            return None

        try:
            decoded = (
                decode_trend_cursor(
                    cursor,
                )
            )
        except TrendCursorError as exc:
            raise BadRequestException(
                message=(
                    "페이지 정보가 "
                    "올바르지 않습니다."
                ),
                data={
                    "reason": (
                        "INVALID_CURSOR"
                    ),
                },
            ) from exc

        if (
            decoded.category_id
            != category_id
        ):
            raise BadRequestException(
                message=(
                    "페이지 정보가 "
                    "올바르지 않습니다."
                ),
                data={
                    "reason": (
                        "INVALID_CURSOR"
                    ),
                },
            )

        return decoded

    def _resolve_filter_category_ids(
        self,
        *,
        category_id: int | None,
    ) -> list[int] | None:
        """요청 Category를 Trend Mapping에 사용할 세부분류 ID로 변환한다."""

        if category_id is None:
            return None

        categories = (
            self.category_repository
            .find_list_by_ids(
                [
                    category_id,
                ]
            )
        )

        if not categories:
            raise NotFoundException(
                message=(
                    "존재하지 않는 "
                    "카테고리입니다."
                ),
                data={
                    "reason": (
                        "CATEGORY_NOT_FOUND"
                    ),
                },
            )

        category = categories[0]

        if not category.is_active:
            self._raise_category_not_available()

        if category.parent_id is None:
            return (
                self._resolve_root_category(
                    category,
                )
            )

        return (
            self._resolve_child_category(
                category,
            )
        )

    def _resolve_root_category(
        self,
        category: Category,
    ) -> list[int]:
        """활성 대분류를 활성 직계 세부분류 집합으로 확장한다."""

        if category.category_code is None:
            self._raise_category_not_available()

        active_categories = (
            self.category_repository
            .find_all_active()
        )

        children = [
            candidate
            for candidate in active_categories
            if (
                candidate.parent_id
                == category.category_id
            )
        ]

        children.sort(
            key=lambda child: (
                child.sort_order,
                child.category_id,
            )
        )

        return [
            child.category_id
            for child in children
        ]

    def _resolve_child_category(
        self,
        category: Category,
    ) -> list[int]:
        """활성 세부분류가 정상 2단계 Taxonomy에 속하는지 검증한다."""

        if category.category_code is not None:
            self._raise_category_not_available()

        parent_id = category.parent_id

        if parent_id is None:
            self._raise_category_not_available()

        parent_categories = (
            self.category_repository
            .find_list_by_ids(
                [
                    parent_id,
                ]
            )
        )

        if not parent_categories:
            self._raise_category_not_available()

        parent = parent_categories[0]

        if (
            not parent.is_active
            or parent.parent_id
            is not None
            or parent.category_code
            is None
        ):
            self._raise_category_not_available()

        return [
            category.category_id,
        ]

    @staticmethod
    def _raise_category_not_available() -> NoReturn:
        """현재 2단계 활성 Category 정책상 필터 불가능함을 알린다."""

        raise BadRequestException(
            message=(
                "현재 사용할 수 없는 "
                "카테고리입니다."
            ),
            data={
                "reason": (
                    "CATEGORY_NOT_AVAILABLE"
                ),
            },
        )

    @classmethod
    def _build_item(
        cls,
        *,
        trend: Trend,
        latest_source: TrendSource | None,
        category_pairs: list[
            tuple[
                Category,
                Category,
            ]
        ],
    ) -> TrendListItem:
        """Trend ORM 조회 결과를 API 응답 항목으로 조립한다."""

        categories = (
            cls._build_categories(
                category_pairs,
            )
        )

        source = None

        if latest_source is not None:
            source = TrendLatestSource(
                source_id=(
                    latest_source.source_id
                ),
                platform=(
                    latest_source.platform
                ),
                source_title=(
                    latest_source.source_title
                ),
                source_url=(
                    latest_source.source_url
                ),
            )

        return TrendListItem(
            trend_id=trend.trend_id,
            title=trend.title,
            summary=trend.summary,
            thumbnail_url=(
                trend.thumbnail_url
            ),
            last_collected_at=(
                cls._as_utc_datetime(
                    trend.last_collected_at,
                )
            ),
            categories=categories,
            latest_source=source,
        )

    @staticmethod
    def _build_categories(
        category_pairs: list[
            tuple[
                Category,
                Category,
            ]
        ],
    ) -> list[TrendCategoryItem]:
        """Category 중복을 제거하고 결정적인 순서로 응답을 구성한다."""

        unique_pairs: dict[
            int,
            tuple[
                Category,
                Category,
            ],
        ] = {}

        for child, parent in (
            category_pairs
        ):
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
                category_id=(
                    child.category_id
                ),
                category_name=(
                    child.category_name
                ),
                parent=TrendCategoryParent(
                    category_id=(
                        parent.category_id
                    ),
                    category_code=(
                        parent.category_code
                    ),
                    category_name=(
                        parent.category_name
                    ),
                ),
            )
            for child, parent
            in ordered_pairs
        ]

    @staticmethod
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
