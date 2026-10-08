from app.core.exceptions import (
    BadRequestException,
    ConflictException,
)
from app.repositories.category_repository import CategoryRepository
from app.repositories.interest_repository import InterestRepository
from app.repositories.trend_repository import TrendRepository
from app.schemas.trend_schema import TrendListData
from app.services.trend_list_item_builder import (
    build_trend_list_item,
)
from app.utils.personalized_trend_cursor import (
    PersonalizedTrendCursor,
    PersonalizedTrendCursorError,
    build_personalized_context_fingerprint,
    decode_personalized_trend_cursor,
    encode_personalized_trend_cursor,
)


class PersonalizedTrendService:
    """사용자 관심사 기반 맞춤 Trend 목록 비즈니스 로직을 담당한다."""

    def __init__(
        self,
        category_repository: CategoryRepository,
        interest_repository: InterestRepository,
        trend_repository: TrendRepository,
    ) -> None:
        self.category_repository = category_repository
        self.interest_repository = interest_repository
        self.trend_repository = trend_repository

    def list_personalized_trends(
        self,
        *,
        user_id: int,
        limit: int,
        cursor: str | None,
    ) -> TrendListData:
        """현재 사용자의 관심사를 기준으로 맞춤 Trend 목록을 조회한다."""

        user_interests = self.interest_repository.find_by_user_id(
            user_id,
        )

        if not user_interests:
            raise ConflictException(
                message="저장된 관심사가 없습니다.",
                data={
                    "reason": "INTERESTS_NOT_INITIALIZED",
                },
            )

        interest_category_ids = [interest.category_id for interest in user_interests]

        interest_categories = self.category_repository.find_list_by_ids(
            interest_category_ids,
        )

        requested_category_ids = set(
            interest_category_ids,
        )

        found_category_ids = {
            category.category_id
            for category in interest_categories
        }

        missing_category_ids = (
            requested_category_ids
            - found_category_ids
        )

        if missing_category_ids:
            raise RuntimeError(
                "저장된 관심사가 존재하지 않는 "
                "Category를 참조합니다. "
                f"missing_category_ids={sorted(missing_category_ids)}"
            )

        active_roots = [
            category
            for category in interest_categories
            if (category.is_active and category.parent_id is None)
        ]

        if not active_roots:
            raise ConflictException(
                message=("현재 관심사로 맞춤 트렌드를 " "조회할 수 없습니다."),
                data={
                    "reason": "INTERESTS_NOT_AVAILABLE",
                },
            )

        active_root_ids = {category.category_id for category in active_roots}

        all_active_categories = self.category_repository.find_all_active()

        effective_child_category_ids = sorted(
            {
                category.category_id
                for category in all_active_categories
                if category.parent_id in active_root_ids
            }
        )

        if not effective_child_category_ids:
            raise ConflictException(
                message=("현재 관심사로 맞춤 트렌드를 " "조회할 수 없습니다."),
                data={
                    "reason": "INTERESTS_NOT_AVAILABLE",
                },
            )

        context_fingerprint = (
            build_personalized_context_fingerprint(
                user_id=user_id,
                effective_child_category_ids=(
                    effective_child_category_ids
                ),
            )
        )

        decoded_cursor: PersonalizedTrendCursor | None = None

        if cursor is not None:
            try:
                decoded_cursor = (
                    decode_personalized_trend_cursor(
                        cursor,
                    )
                )
            except PersonalizedTrendCursorError as exc:
                raise BadRequestException(
                    message="페이지 정보가 올바르지 않습니다.",
                    data={
                        "reason": "INVALID_CURSOR",
                    },
                ) from exc

            if (
                decoded_cursor.context_fingerprint
                != context_fingerprint
            ):
                raise BadRequestException(
                    message="페이지 정보가 올바르지 않습니다.",
                    data={
                        "reason": "INVALID_CURSOR",
                    },
                )

        page_rows = self.trend_repository.find_page(
            limit=limit + 1,
            category_ids=effective_child_category_ids,
            cursor_last_collected_at=(
                decoded_cursor.last_collected_at
                if decoded_cursor is not None
                else None
            ),
            cursor_trend_id=(
                decoded_cursor.trend_id
                if decoded_cursor is not None
                else None
            ),
        )

        if not page_rows:
            return TrendListData(
                items=[],
                next_cursor=None,
                has_next=False,
            )

        has_next = len(page_rows) > limit

        response_trends = page_rows[:limit]

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
            build_trend_list_item(
                trend=trend,
                latest_source=latest_sources.get(
                    trend.trend_id,
                ),
                category_pairs=categories_by_trend_id.get(
                    trend.trend_id,
                    [],
                ),
            )
            for trend in response_trends
        ]

        next_cursor = None

        if has_next:
            last_returned = response_trends[-1]

            next_cursor = encode_personalized_trend_cursor(
                PersonalizedTrendCursor(
                    last_collected_at=(
                        last_returned.last_collected_at
                    ),
                    trend_id=last_returned.trend_id,
                    context_fingerprint=context_fingerprint,
                )
            )

        return TrendListData(
            items=items,
            next_cursor=next_cursor,
            has_next=has_next,
        )
