from datetime import datetime
from typing import cast
from unittest.mock import Mock

import pytest

from app.core.exceptions import (
    BadRequestException,
    NotFoundException,
)
from app.models.category import Category
from app.models.db_enums import (
    CategoryCode,
    TrendSourcePlatform,
    TrendStatus,
)
from app.models.trend import Trend
from app.models.trend_source import TrendSource
from app.repositories.category_repository import (
    CategoryRepository,
)
from app.services.trend_service import (
    TrendService,
)
from app.utils.trend_cursor import (
    TrendCursor,
    decode_trend_cursor,
    encode_trend_cursor,
)


def make_category(
    category_id: int,
    *,
    category_name: str | None = None,
    category_code: CategoryCode | None = None,
    is_active: bool = True,
    parent_id: int | None = None,
    sort_order: int = 1,
) -> Category:
    """TrendService 테스트용 Category를 생성한다."""

    return Category(
        category_id=category_id,
        category_code=category_code,
        category_name=(
            category_name
            or f"카테고리 {category_id}"
        ),
        parent_id=parent_id,
        sort_order=sort_order,
        is_active=is_active,
    )


def make_trend(
    trend_id: int,
    *,
    collected_at: datetime,
    summary: str | None = "테스트 요약",
    thumbnail_url: str | None = (
        "https://example.com/image.jpg"
    ),
) -> Trend:
    """TrendService 테스트용 Trend를 생성한다."""

    return Trend(
        trend_id=trend_id,
        title=f"테스트 트렌드 {trend_id}",
        normalized_title=(
            f"test-trend-{trend_id}"
        ),
        summary=summary,
        thumbnail_url=thumbnail_url,
        status=TrendStatus.ACTIVE,
        first_collected_at=collected_at,
        last_collected_at=collected_at,
        updated_at=None,
    )


def make_source(
    *,
    source_id: int,
    trend_id: int,
    collected_at: datetime,
    source_title: str | None = (
        "테스트 출처"
    ),
) -> TrendSource:
    """TrendService 테스트용 Source를 생성한다."""

    return TrendSource(
        source_id=source_id,
        source_key=(
            f"{source_id:064d}"
        ),
        source_url=(
            "https://example.com/source"
        ),
        source_title=source_title,
        platform=TrendSourcePlatform.YOUTUBE,
        collected_at=collected_at,
        external_id=None,
        trend_id=trend_id,
    )


def make_service() -> tuple[
    TrendService,
    Mock,
    Mock,
]:
    """Mock Repository를 사용하는 TrendService를 생성한다."""

    category_repository_mock = Mock(
        spec=CategoryRepository,
    )
    trend_repository_mock = Mock()

    category_repository_mock.find_list_by_ids.return_value = []
    category_repository_mock.find_all_active.return_value = []

    trend_repository_mock.find_page.return_value = []
    trend_repository_mock.find_latest_sources_by_trend_ids.return_value = {}
    trend_repository_mock.find_categories_by_trend_ids.return_value = {}

    service = TrendService(
        category_repository=cast(
            CategoryRepository,
            category_repository_mock,
        ),
        trend_repository=trend_repository_mock,
    )

    return (
        service,
        category_repository_mock,
        trend_repository_mock,
    )


def test_list_trends_returns_empty_page_without_batch_queries() -> None:
    """조회 결과가 없으면 관련 Source/Category Batch Query를 생략한다."""

    (
        service,
        category_repository_mock,
        trend_repository_mock,
    ) = make_service()

    result = service.list_trends(
        category_id=None,
        limit=20,
        cursor=None,
    )

    assert result.model_dump() == {
        "items": [],
        "next_cursor": None,
        "has_next": False,
    }

    category_repository_mock.find_list_by_ids.assert_not_called()
    category_repository_mock.find_all_active.assert_not_called()

    trend_repository_mock.find_page.assert_called_once_with(
        limit=21,
        category_ids=None,
        cursor_last_collected_at=None,
        cursor_trend_id=None,
    )

    trend_repository_mock.find_latest_sources_by_trend_ids.assert_not_called()
    trend_repository_mock.find_categories_by_trend_ids.assert_not_called()


def test_list_trends_uses_limit_plus_one_and_last_returned_item_for_cursor() -> None:
    """초과 조회 행은 has_next 판정에만 사용한다."""

    (
        service,
        _,
        trend_repository_mock,
    ) = make_service()

    newest = make_trend(
        103,
        collected_at=datetime(
            2026,
            9,
            26,
            12,
            0,
            3,
        ),
    )
    last_returned = make_trend(
        102,
        collected_at=datetime(
            2026,
            9,
            26,
            12,
            0,
            2,
        ),
    )
    overflow = make_trend(
        101,
        collected_at=datetime(
            2026,
            9,
            26,
            12,
            0,
            1,
        ),
    )

    trend_repository_mock.find_page.return_value = [
        newest,
        last_returned,
        overflow,
    ]

    result = service.list_trends(
        category_id=None,
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

    decoded_cursor = decode_trend_cursor(
        result.next_cursor,
    )

    assert decoded_cursor == TrendCursor(
        last_collected_at=(
            last_returned.last_collected_at
        ),
        trend_id=102,
        category_id=None,
    )

    assert decoded_cursor.trend_id != (
        overflow.trend_id
    )

    trend_repository_mock.find_page.assert_called_once_with(
        limit=3,
        category_ids=None,
        cursor_last_collected_at=None,
        cursor_trend_id=None,
    )

    trend_repository_mock.find_latest_sources_by_trend_ids.assert_called_once_with(
        [
            103,
            102,
        ]
    )
    trend_repository_mock.find_categories_by_trend_ids.assert_called_once_with(
        [
            103,
            102,
        ]
    )


def test_list_trends_returns_nullable_fields_and_missing_source() -> None:
    """nullable 필드와 Source 부재는 정상 목록 결과로 조립한다."""

    (
        service,
        _,
        trend_repository_mock,
    ) = make_service()

    trend = make_trend(
        101,
        collected_at=datetime(
            2026,
            9,
            26,
            12,
            0,
            0,
        ),
        summary=None,
        thumbnail_url=None,
    )

    trend_repository_mock.find_page.return_value = [
        trend,
    ]

    result = service.list_trends(
        category_id=None,
        limit=20,
        cursor=None,
    )

    assert len(result.items) == 1

    item = result.items[0]

    assert item.summary is None
    assert item.thumbnail_url is None
    assert item.latest_source is None
    assert item.categories == []

    assert result.has_next is False
    assert result.next_cursor is None


def test_list_trends_builds_latest_source_and_all_categories() -> None:
    """응답에는 최신 Source와 연결된 Category 전체를 조립한다."""

    (
        service,
        _,
        trend_repository_mock,
    ) = make_service()

    trend = make_trend(
        101,
        collected_at=datetime(
            2026,
            9,
            26,
            12,
            0,
            0,
        ),
    )

    source = make_source(
        source_id=500,
        trend_id=101,
        collected_at=datetime(
            2026,
            9,
            26,
            11,
            50,
            0,
        ),
        source_title=None,
    )

    game = make_category(
        1,
        category_name="게임",
        category_code=CategoryCode.GAME,
        sort_order=2,
    )
    mobile_game = make_category(
        11,
        category_name="모바일 게임",
        parent_id=1,
        sort_order=2,
    )
    pc_game = make_category(
        12,
        category_name="PC 게임",
        parent_id=1,
        sort_order=1,
    )

    trend_repository_mock.find_page.return_value = [
        trend,
    ]
    trend_repository_mock.find_latest_sources_by_trend_ids.return_value = {
        101: source,
    }

    # Repository 결과 순서에 의존하지 않는지 확인하기 위해
    # 의도적으로 sort_order 역순으로 전달한다.
    trend_repository_mock.find_categories_by_trend_ids.return_value = {
        101: [
            (
                mobile_game,
                game,
            ),
            (
                pc_game,
                game,
            ),
        ],
    }

    result = service.list_trends(
        category_id=None,
        limit=20,
        cursor=None,
    )

    item = result.items[0]

    assert item.latest_source is not None
    assert item.latest_source.source_id == 500
    assert item.latest_source.source_title is None
    assert (
        item.latest_source.platform
        == TrendSourcePlatform.YOUTUBE
    )

    assert [
        category.category_id
        for category in item.categories
    ] == [
        12,
        11,
    ]

    assert [
        category.parent.category_id
        for category in item.categories
    ] == [
        1,
        1,
    ]


def test_list_trends_expands_active_root_to_direct_active_children() -> None:
    """활성 대분류 필터는 활성 직계 세부분류 ID 집합으로 확장한다."""

    (
        service,
        category_repository_mock,
        trend_repository_mock,
    ) = make_service()

    root = make_category(
        1,
        category_name="게임",
        category_code=CategoryCode.GAME,
        sort_order=1,
    )
    mobile = make_category(
        11,
        category_name="모바일 게임",
        parent_id=1,
        sort_order=1,
    )
    pc = make_category(
        12,
        category_name="PC 게임",
        parent_id=1,
        sort_order=2,
    )
    unrelated = make_category(
        21,
        category_name="인공지능",
        parent_id=2,
        sort_order=1,
    )

    category_repository_mock.find_list_by_ids.return_value = [
        root,
    ]
    category_repository_mock.find_all_active.return_value = [
        root,
        mobile,
        pc,
        unrelated,
    ]

    service.list_trends(
        category_id=1,
        limit=20,
        cursor=None,
    )

    trend_repository_mock.find_page.assert_called_once_with(
        limit=21,
        category_ids=[
            11,
            12,
        ],
        cursor_last_collected_at=None,
        cursor_trend_id=None,
    )


def test_list_trends_returns_empty_when_root_has_no_active_children() -> None:
    """활성 직계 세부분류가 없는 대분류는 정상 빈 목록이다."""

    (
        service,
        category_repository_mock,
        trend_repository_mock,
    ) = make_service()

    root = make_category(
        1,
        category_name="게임",
        category_code=CategoryCode.GAME,
    )

    category_repository_mock.find_list_by_ids.return_value = [
        root,
    ]
    category_repository_mock.find_all_active.return_value = [
        root,
    ]

    result = service.list_trends(
        category_id=1,
        limit=20,
        cursor=None,
    )

    assert result.items == []
    assert result.has_next is False
    assert result.next_cursor is None

    trend_repository_mock.find_page.assert_not_called()


def test_list_trends_filters_directly_by_active_child() -> None:
    """활성 세부분류는 자신의 ID로 직접 필터한다."""

    (
        service,
        category_repository_mock,
        trend_repository_mock,
    ) = make_service()

    parent = make_category(
        1,
        category_name="게임",
        category_code=CategoryCode.GAME,
    )
    child = make_category(
        11,
        category_name="모바일 게임",
        category_code=None,
        parent_id=1,
    )

    category_repository_mock.find_list_by_ids.side_effect = [
        [
            child,
        ],
        [
            parent,
        ],
    ]

    service.list_trends(
        category_id=11,
        limit=20,
        cursor=None,
    )

    trend_repository_mock.find_page.assert_called_once_with(
        limit=21,
        category_ids=[
            11,
        ],
        cursor_last_collected_at=None,
        cursor_trend_id=None,
    )


def test_list_trends_raises_not_found_for_missing_category() -> None:
    """존재하지 않는 Category 필터는 404로 처리한다."""

    (
        service,
        category_repository_mock,
        trend_repository_mock,
    ) = make_service()

    category_repository_mock.find_list_by_ids.return_value = []

    with pytest.raises(
        NotFoundException,
    ) as exc_info:
        service.list_trends(
            category_id=999,
            limit=20,
            cursor=None,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.data == {
        "reason": "CATEGORY_NOT_FOUND",
    }

    trend_repository_mock.find_page.assert_not_called()


def test_list_trends_rejects_inactive_category() -> None:
    """비활성 Category는 필터로 사용할 수 없다."""

    (
        service,
        category_repository_mock,
        trend_repository_mock,
    ) = make_service()

    inactive = make_category(
        1,
        is_active=False,
    )

    category_repository_mock.find_list_by_ids.return_value = [
        inactive,
    ]

    with pytest.raises(
        BadRequestException,
    ) as exc_info:
        service.list_trends(
            category_id=1,
            limit=20,
            cursor=None,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.data == {
        "reason": "CATEGORY_NOT_AVAILABLE",
    }

    trend_repository_mock.find_page.assert_not_called()


def test_list_trends_rejects_active_child_under_inactive_parent() -> None:
    """활성 자식이라도 비활성 부모 아래 있으면 필터 선택지와 일치하지 않는다."""

    (
        service,
        category_repository_mock,
        trend_repository_mock,
    ) = make_service()

    child = make_category(
        11,
        parent_id=1,
        is_active=True,
    )
    inactive_parent = make_category(
        1,
        category_code=CategoryCode.GAME,
        is_active=False,
    )

    category_repository_mock.find_list_by_ids.side_effect = [
        [
            child,
        ],
        [
            inactive_parent,
        ],
    ]

    with pytest.raises(
        BadRequestException,
    ) as exc_info:
        service.list_trends(
            category_id=11,
            limit=20,
            cursor=None,
        )

    assert exc_info.value.data == {
        "reason": "CATEGORY_NOT_AVAILABLE",
    }

    trend_repository_mock.find_page.assert_not_called()


def test_list_trends_rejects_third_level_category() -> None:
    """2단계 Taxonomy를 벗어난 3단계 Category는 필터로 허용하지 않는다."""

    (
        service,
        category_repository_mock,
        trend_repository_mock,
    ) = make_service()

    third_level = make_category(
        30,
        parent_id=20,
    )
    second_level_parent = make_category(
        20,
        parent_id=10,
    )

    category_repository_mock.find_list_by_ids.side_effect = [
        [
            third_level,
        ],
        [
            second_level_parent,
        ],
    ]

    with pytest.raises(
        BadRequestException,
    ) as exc_info:
        service.list_trends(
            category_id=30,
            limit=20,
            cursor=None,
        )

    assert exc_info.value.data == {
        "reason": "CATEGORY_NOT_AVAILABLE",
    }

    trend_repository_mock.find_page.assert_not_called()


def test_list_trends_rejects_cursor_from_other_category_context() -> None:
    """다른 Category 필터에서 발급된 Cursor를 재사용할 수 없다."""

    (
        service,
        category_repository_mock,
        trend_repository_mock,
    ) = make_service()

    cursor = encode_trend_cursor(
        TrendCursor(
            last_collected_at=datetime(
                2026,
                9,
                26,
                12,
                0,
                0,
                123456,
            ),
            trend_id=101,
            category_id=1,
        ),
    )

    with pytest.raises(
        BadRequestException,
    ) as exc_info:
        service.list_trends(
            category_id=2,
            limit=20,
            cursor=cursor,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.data == {
        "reason": "INVALID_CURSOR",
    }

    category_repository_mock.find_list_by_ids.assert_not_called()
    trend_repository_mock.find_page.assert_not_called()


def test_list_trends_converts_invalid_cursor_to_bad_request() -> None:
    """잘못된 Cursor는 INVALID_CURSOR 400으로 변환한다."""

    (
        service,
        category_repository_mock,
        trend_repository_mock,
    ) = make_service()

    with pytest.raises(
        BadRequestException,
    ) as exc_info:
        service.list_trends(
            category_id=None,
            limit=20,
            cursor="invalid-cursor",
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.data == {
        "reason": "INVALID_CURSOR",
    }

    category_repository_mock.find_list_by_ids.assert_not_called()
    trend_repository_mock.find_page.assert_not_called()


def test_list_trends_passes_cursor_boundary_to_repository() -> None:
    """정상 Cursor 경계값을 변경 없이 Repository에 전달한다."""

    (
        service,
        _,
        trend_repository_mock,
    ) = make_service()

    last_collected_at = datetime(
        2026,
        9,
        26,
        12,
        30,
        15,
        123456,
    )

    cursor = encode_trend_cursor(
        TrendCursor(
            last_collected_at=(
                last_collected_at
            ),
            trend_id=321,
            category_id=None,
        )
    )

    trend_repository_mock.find_page.return_value = []

    service.list_trends(
        category_id=None,
        limit=20,
        cursor=cursor,
    )

    trend_repository_mock.find_page.assert_called_once_with(
        limit=21,
        category_ids=None,
        cursor_last_collected_at=(
            last_collected_at
        ),
        cursor_trend_id=321,
    )


def test_list_trends_deduplicates_and_orders_categories() -> None:
    """Category를 중복 제거하고 부모/자식 순서로 결정적으로 정렬한다."""
    (
        service,
        _,
        trend_repository_mock,
    ) = make_service()

    trend = make_trend(
        101,
        collected_at=datetime(
            2026,
            9,
            26,
            12,
            0,
            0,
        ),
    )

    game = make_category(
        1,
        category_name="게임",
        category_code=CategoryCode.GAME,
        sort_order=2,
    )
    food = make_category(
        2,
        category_name="음식",
        category_code=CategoryCode.FOOD,
        sort_order=1,
    )

    pc_game = make_category(
        11,
        category_name="PC 게임",
        parent_id=1,
        sort_order=1,
    )
    dessert = make_category(
        21,
        category_name="디저트",
        parent_id=2,
        sort_order=2,
    )

    trend_repository_mock.find_page.return_value = [
        trend,
    ]

    trend_repository_mock.find_categories_by_trend_ids.return_value = {
        101: [
            (
                pc_game,
                game,
            ),
            (
                pc_game,
                game,
            ),
            (
                dessert,
                food,
            ),
        ],
    }

    result = service.list_trends(
        category_id=None,
        limit=20,
        cursor=None,
    )

    assert [
        category.category_id
        for category
        in result.items[0].categories
    ] == [
        21,
        11,
    ]
