from datetime import UTC, datetime
from typing import cast
from unittest.mock import Mock

import pytest

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
)
from app.models.category import Category
from app.models.db_enums import (
    CategoryCode,
    TrendStatus,
)
from app.models.trend import Trend
from app.models.user_interest_category import (
    UserInterestCategory,
)
from app.repositories.category_repository import (
    CategoryRepository,
)
from app.repositories.interest_repository import (
    InterestRepository,
)
from app.repositories.trend_repository import (
    TrendRepository,
)
from app.services.personalized_trend_service import (
    PersonalizedTrendService,
)
from app.utils.personalized_trend_cursor import (
    PersonalizedTrendCursor,
    build_personalized_context_fingerprint,
    decode_personalized_trend_cursor,
    encode_personalized_trend_cursor,
)


def make_category(
    category_id: int,
    *,
    category_code: CategoryCode | None = None,
    is_active: bool = True,
    parent_id: int | None = None,
) -> Category:
    """PersonalizedTrendService 테스트용 Category를 생성한다."""

    return Category(
        category_id=category_id,
        category_code=category_code,
        category_name=f"카테고리 {category_id}",
        parent_id=parent_id,
        sort_order=1,
        is_active=is_active,
    )

def make_trend(
    trend_id: int,
    *,
    collected_at: datetime,
) -> Trend:
    """PersonalizedTrendService 테스트용 Trend를 생성한다."""

    return Trend(
        trend_id=trend_id,
        title=f"테스트 트렌드 {trend_id}",
        normalized_title=f"test-trend-{trend_id}",
        summary="테스트 요약",
        thumbnail_url=None,
        status=TrendStatus.ACTIVE,
        first_collected_at=collected_at,
        last_collected_at=collected_at,
        updated_at=None,
    )


def make_user_interest(
    *,
    user_id: int,
    category_id: int,
) -> UserInterestCategory:
    """PersonalizedTrendService 테스트용 관심사 Row를 생성한다."""

    return UserInterestCategory(
        user_id=user_id,
        category_id=category_id,
    )


def make_service() -> tuple[
    PersonalizedTrendService,
    Mock,
    Mock,
    Mock,
]:
    """Mock Repository를 사용하는 PersonalizedTrendService를 생성한다."""

    category_repository_mock = Mock(
        spec=CategoryRepository,
    )
    interest_repository_mock = Mock(
        spec=InterestRepository,
    )
    trend_repository_mock = Mock(
        spec=TrendRepository,
    )

    service = PersonalizedTrendService(
        category_repository=cast(
            CategoryRepository,
            category_repository_mock,
        ),
        interest_repository=cast(
            InterestRepository,
            interest_repository_mock,
        ),
        trend_repository=cast(
            TrendRepository,
            trend_repository_mock,
        ),
    )

    return (
        service,
        category_repository_mock,
        interest_repository_mock,
        trend_repository_mock,
    )


def test_list_personalized_trends_rejects_uninitialized_interests() -> None:
    """저장된 관심사 Row가 없으면 미초기화 상태로 처리한다."""

    (
        service,
        category_repository_mock,
        interest_repository_mock,
        trend_repository_mock,
    ) = make_service()

    interest_repository_mock.find_by_user_id.return_value = []

    with pytest.raises(
        ConflictException,
    ) as exc_info:
        service.list_personalized_trends(
            user_id=15,
            limit=20,
            cursor=None,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.data == {
        "reason": "INTERESTS_NOT_INITIALIZED",
    }

    interest_repository_mock.find_by_user_id.assert_called_once_with(
        15,
    )

    category_repository_mock.find_list_by_ids.assert_not_called()
    category_repository_mock.find_all_active.assert_not_called()

    trend_repository_mock.find_page.assert_not_called()
    trend_repository_mock.find_latest_sources_by_trend_ids.assert_not_called()
    trend_repository_mock.find_categories_by_trend_ids.assert_not_called()


def test_list_personalized_trends_rejects_when_only_root_is_inactive() -> None:
    """Interest row는 있지만 사용할 수 있는 활성 Root가 없으면 거부한다."""

    (
        service,
        category_repository_mock,
        interest_repository_mock,
        trend_repository_mock,
    ) = make_service()

    user_interest = make_user_interest(
        user_id=15,
        category_id=1,
    )
    inactive_root = make_category(
        1,
        category_code=CategoryCode.GAME,
        is_active=False,
        parent_id=None,
    )

    interest_repository_mock.find_by_user_id.return_value = [
        user_interest,
    ]
    category_repository_mock.find_list_by_ids.return_value = [
        inactive_root,
    ]

    with pytest.raises(
        ConflictException,
    ) as exc_info:
        service.list_personalized_trends(
            user_id=15,
            limit=20,
            cursor=None,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.data == {
        "reason": "INTERESTS_NOT_AVAILABLE",
    }

    interest_repository_mock.find_by_user_id.assert_called_once_with(
        15,
    )
    category_repository_mock.find_list_by_ids.assert_called_once_with(
        [
            1,
        ],
    )

    category_repository_mock.find_all_active.assert_not_called()

    trend_repository_mock.find_page.assert_not_called()
    trend_repository_mock.find_latest_sources_by_trend_ids.assert_not_called()
    trend_repository_mock.find_categories_by_trend_ids.assert_not_called()


def test_list_personalized_trends_rejects_when_root_has_no_active_children() -> None:
    """활성 Root가 있어도 활성 직속 Child가 없으면 맞춤 조회가 불가능하다."""

    (
        service,
        category_repository_mock,
        interest_repository_mock,
        trend_repository_mock,
    ) = make_service()

    user_interest = make_user_interest(
        user_id=15,
        category_id=1,
    )
    active_root = make_category(
        1,
        category_code=CategoryCode.GAME,
        is_active=True,
        parent_id=None,
    )

    interest_repository_mock.find_by_user_id.return_value = [
        user_interest,
    ]
    category_repository_mock.find_list_by_ids.return_value = [
        active_root,
    ]
    category_repository_mock.find_all_active.return_value = [
        active_root,
    ]

    with pytest.raises(
        ConflictException,
    ) as exc_info:
        service.list_personalized_trends(
            user_id=15,
            limit=20,
            cursor=None,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.data == {
        "reason": "INTERESTS_NOT_AVAILABLE",
    }

    category_repository_mock.find_all_active.assert_called_once_with()

    trend_repository_mock.find_page.assert_not_called()
    trend_repository_mock.find_latest_sources_by_trend_ids.assert_not_called()
    trend_repository_mock.find_categories_by_trend_ids.assert_not_called()


def test_list_personalized_trends_uses_child_scope_for_empty_page() -> None:
    """활성 직속 Child 집합으로 조회하고 Trend가 없으면 빈 목록을 반환한다."""

    (
        service,
        category_repository_mock,
        interest_repository_mock,
        trend_repository_mock,
    ) = make_service()

    game_root = make_category(
        1,
        category_code=CategoryCode.GAME,
    )
    food_root = make_category(
        2,
        category_code=CategoryCode.FOOD,
    )

    mobile_game = make_category(
        11,
        parent_id=1,
    )
    pc_game = make_category(
        12,
        parent_id=1,
    )
    dessert = make_category(
        21,
        parent_id=2,
    )

    interest_repository_mock.find_by_user_id.return_value = [
        make_user_interest(
            user_id=15,
            category_id=1,
        ),
    ]

    category_repository_mock.find_list_by_ids.return_value = [
        game_root,
    ]

    category_repository_mock.find_all_active.return_value = [
        dessert,
        pc_game,
        food_root,
        mobile_game,
        game_root,
    ]

    trend_repository_mock.find_page.return_value = []

    result = service.list_personalized_trends(
        user_id=15,
        limit=20,
        cursor=None,
    )

    assert result.model_dump() == {
        "items": [],
        "next_cursor": None,
        "has_next": False,
    }

    category_repository_mock.find_list_by_ids.assert_called_once_with(
        [1],
    )
    category_repository_mock.find_all_active.assert_called_once_with()

    trend_repository_mock.find_page.assert_called_once_with(
        limit=21,
        category_ids=[11, 12],
        cursor_last_collected_at=None,
        cursor_trend_id=None,
    )

    trend_repository_mock.find_latest_sources_by_trend_ids.assert_not_called()
    trend_repository_mock.find_categories_by_trend_ids.assert_not_called()


def test_list_personalized_trends_returns_single_trend_item() -> None:
    """유효한 Child Scope에 일치하는 Trend를 목록 항목으로 반환한다."""

    (
        service,
        category_repository_mock,
        interest_repository_mock,
        trend_repository_mock,
    ) = make_service()

    game_root = make_category(
        1,
        category_code=CategoryCode.GAME,
    )
    mobile_game = make_category(
        11,
        parent_id=1,
    )

    collected_at = datetime(
        2026,
        10,
        8,
        12,
        0,
        0,
    )

    trend = make_trend(
        101,
        collected_at=collected_at,
    )

    interest_repository_mock.find_by_user_id.return_value = [
        make_user_interest(
            user_id=15,
            category_id=1,
        ),
    ]

    category_repository_mock.find_list_by_ids.return_value = [
        game_root,
    ]
    category_repository_mock.find_all_active.return_value = [
        game_root,
        mobile_game,
    ]

    trend_repository_mock.find_page.return_value = [
        trend,
    ]
    trend_repository_mock.find_latest_sources_by_trend_ids.return_value = {}
    trend_repository_mock.find_categories_by_trend_ids.return_value = {}

    result = service.list_personalized_trends(
        user_id=15,
        limit=20,
        cursor=None,
    )

    assert len(result.items) == 1

    item = result.items[0]

    assert item.trend_id == 101
    assert item.title == "테스트 트렌드 101"
    assert item.summary == "테스트 요약"
    assert item.thumbnail_url is None
    assert item.latest_source is None
    assert item.categories == []

    assert item.last_collected_at == (
        collected_at.replace(
            tzinfo=UTC,
        )
    )

    assert result.has_next is False
    assert result.next_cursor is None

    trend_repository_mock.find_page.assert_called_once_with(
        limit=21,
        category_ids=[11],
        cursor_last_collected_at=None,
        cursor_trend_id=None,
    )

    trend_repository_mock.find_latest_sources_by_trend_ids.assert_called_once_with(
        [101],
    )
    trend_repository_mock.find_categories_by_trend_ids.assert_called_once_with(
        [101],
    )


def test_list_personalized_trends_uses_last_returned_trend_for_cursor() -> None:
    """초과 조회 행은 제외하고 마지막 응답 Trend로 Cursor를 발급한다."""

    (
        service,
        category_repository_mock,
        interest_repository_mock,
        trend_repository_mock,
    ) = make_service()

    game_root = make_category(
        1,
        category_code=CategoryCode.GAME,
    )
    mobile_game = make_category(
        11,
        parent_id=1,
    )

    interest_repository_mock.find_by_user_id.return_value = [
        make_user_interest(
            user_id=15,
            category_id=1,
        ),
    ]

    category_repository_mock.find_list_by_ids.return_value = [
        game_root,
    ]
    category_repository_mock.find_all_active.return_value = [
        game_root,
        mobile_game,
    ]

    newest = make_trend(
        103,
        collected_at=datetime(
            2026, 10, 8, 12, 0, 3,
        ),
    )
    last_returned = make_trend(
        102,
        collected_at=datetime(
            2026, 10, 8, 12, 0, 2,
        ),
    )
    overflow = make_trend(
        101,
        collected_at=datetime(
            2026, 10, 8, 12, 0, 1,
        ),
    )

    trend_repository_mock.find_page.return_value = [
        newest,
        last_returned,
        overflow,
    ]
    trend_repository_mock.find_latest_sources_by_trend_ids.return_value = {}
    trend_repository_mock.find_categories_by_trend_ids.return_value = {}

    result = service.list_personalized_trends(
        user_id=15,
        limit=2,
        cursor=None,
    )

    assert [
        item.trend_id
        for item in result.items
    ] == [
        103,
        102,
    ]

    assert result.has_next is True
    assert result.next_cursor is not None

    decoded_cursor = decode_personalized_trend_cursor(
        result.next_cursor,
    )

    expected_fingerprint = build_personalized_context_fingerprint(
        user_id=15,
        effective_child_category_ids=[11],
    )

    assert decoded_cursor == PersonalizedTrendCursor(
        last_collected_at=last_returned.last_collected_at,
        trend_id=102,
        context_fingerprint=expected_fingerprint,
    )

    trend_repository_mock.find_page.assert_called_once_with(
        limit=3,
        category_ids=[11],
        cursor_last_collected_at=None,
        cursor_trend_id=None,
    )

    trend_repository_mock.find_latest_sources_by_trend_ids.assert_called_once_with(
        [103, 102],
    )
    trend_repository_mock.find_categories_by_trend_ids.assert_called_once_with(
        [103, 102],
    )


def test_list_personalized_trends_rejects_stale_scope_cursor() -> None:
    """현재 Child Scope와 다른 Cursor는 조회 전에 거부한다."""

    (
        service,
        category_repository_mock,
        interest_repository_mock,
        trend_repository_mock,
    ) = make_service()

    game_root = make_category(
        1,
        category_code=CategoryCode.GAME,
    )

    mobile_game = make_category(
        11,
        parent_id=1,
    )

    interest_repository_mock.find_by_user_id.return_value = [
        make_user_interest(
            user_id=15,
            category_id=1,
        ),
    ]

    category_repository_mock.find_list_by_ids.return_value = [
        game_root,
    ]

    # 현재는 Child 11만 활성 상태
    category_repository_mock.find_all_active.return_value = [
        game_root,
        mobile_game,
    ]

    # 이전에는 Child 11과 12가 모두 활성 상태였음
    old_fingerprint = build_personalized_context_fingerprint(
        user_id=15,
        effective_child_category_ids=[11, 12],
    )

    old_cursor = encode_personalized_trend_cursor(
        PersonalizedTrendCursor(
            last_collected_at=datetime(
                2026, 10, 8, 12, 0, 0,
            ),
            trend_id=103,
            context_fingerprint=old_fingerprint,
        )
    )

    # 현재 미구현 코드는 빈 목록을 정상 반환하게 설정
    trend_repository_mock.find_page.return_value = []

    with pytest.raises(
        BadRequestException,
    ) as exc_info:
        service.list_personalized_trends(
            user_id=15,
            limit=20,
            cursor=old_cursor,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.data == {
        "reason": "INVALID_CURSOR",
    }

    # Cursor가 유효하지 않으므로 Trend 조회 금지
    trend_repository_mock.find_page.assert_not_called()
    trend_repository_mock.find_latest_sources_by_trend_ids.assert_not_called()
    trend_repository_mock.find_categories_by_trend_ids.assert_not_called()


def test_list_personalized_trends_applies_valid_cursor_boundary() -> None:
    """유효한 Cursor의 정렬 경계값을 Repository 조회에 전달한다."""

    (
        service,
        category_repository_mock,
        interest_repository_mock,
        trend_repository_mock,
    ) = make_service()

    game_root = make_category(
        1,
        category_code=CategoryCode.GAME,
    )

    mobile_game = make_category(
        11,
        parent_id=1,
    )

    interest_repository_mock.find_by_user_id.return_value = [
        make_user_interest(
            user_id=15,
            category_id=1,
        ),
    ]

    category_repository_mock.find_list_by_ids.return_value = [
        game_root,
    ]

    category_repository_mock.find_all_active.return_value = [
        game_root,
        mobile_game,
    ]

    cursor_collected_at = datetime(
        2026,
        10,
        8,
        12,
        0,
        2,
        tzinfo=UTC,
    )

    fingerprint = build_personalized_context_fingerprint(
        user_id=15,
        effective_child_category_ids=[11],
    )

    valid_cursor = encode_personalized_trend_cursor(
        PersonalizedTrendCursor(
            last_collected_at=cursor_collected_at,
            trend_id=102,
            context_fingerprint=fingerprint,
        )
    )

    trend_repository_mock.find_page.return_value = []

    result = service.list_personalized_trends(
        user_id=15,
        limit=20,
        cursor=valid_cursor,
    )

    assert result.model_dump() == {
        "items": [],
        "next_cursor": None,
        "has_next": False,
    }

    trend_repository_mock.find_page.assert_called_once_with(
        limit=21,
        category_ids=[11],
        cursor_last_collected_at=cursor_collected_at,
        cursor_trend_id=102,
    )

    trend_repository_mock.find_latest_sources_by_trend_ids.assert_not_called()
    trend_repository_mock.find_categories_by_trend_ids.assert_not_called()
