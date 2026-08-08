import logging
from typing import cast
from unittest.mock import Mock

import pytest

from app.models.category import Category
from app.models.db_enums import CategoryCode
from app.repositories.category_repository import CategoryRepository
from app.services.category_service import CategoryService


def make_category(
    category_id: int,
    category_name: str,
    sort_order: int,
    parent_id: int | None = None,
    category_code: CategoryCode | None = None,
) -> Category:
    return Category(
        category_id=category_id,
        category_code=category_code,
        category_name=category_name,
        parent_id=parent_id,
        sort_order=sort_order,
        is_active=True,
    )


def make_service(
    categories: list[Category],
) -> tuple[CategoryService, Mock]:
    """지정된 카테고리를 반환하는 Mock Repository를 구성한다."""

    repository_mock = Mock(
        spec=CategoryRepository,
    )
    repository_mock.find_all_active.return_value = categories

    service = CategoryService(
        category_repository=cast(
            CategoryRepository,
            repository_mock,
        ),
    )

    return service, repository_mock


def test_list_categories_returns_empty_list() -> None:
    """조회 결과가 없으면 빈 categories 배열을 반환한다."""

    service, repository_mock = make_service([])

    result = service.list_categories()

    assert result.model_dump() == {
        "categories": [],
    }
    repository_mock.find_all_active.assert_called_once_with()


def test_list_categories_builds_two_level_hierarchy() -> None:
    """대분류와 세부분류를 2단계 계층으로 조립한다."""

    categories = [
        make_category(
            category_id=1,
            category_code=CategoryCode.GAME,
            category_name="게임",
            sort_order=1,
        ),
        make_category(
            category_id=3,
            category_code=None,
            category_name="모바일 게임",
            parent_id=1,
            sort_order=1,
        ),
        make_category(
            category_id=2,
            category_code=CategoryCode.IT_DIGITAL,
            category_name="IT/디지털",
            sort_order=2,
        ),
        make_category(
            category_id=4,
            category_code=None,
            category_name="PC 게임",
            parent_id=1,
            sort_order=2,
        ),
        make_category(
            category_id=5,
            category_code=None,
            category_name="인공지능",
            parent_id=2,
            sort_order=1,
        ),
    ]

    service, repository_mock = make_service(categories)

    result = service.list_categories()

    assert result.model_dump() == {
        "categories": [
            {
                "category_id": 1,
                "category_code": CategoryCode.GAME,
                "category_name": "게임",
                "parent_id": None,
                "sort_order": 1,
                "children": [
                    {
                        "category_id": 3,
                        "category_code": None,
                        "category_name": "모바일 게임",
                        "parent_id": 1,
                        "sort_order": 1,
                        "children": [],
                    },
                    {
                        "category_id": 4,
                        "category_code": None,
                        "category_name": "PC 게임",
                        "parent_id": 1,
                        "sort_order": 2,
                        "children": [],
                    },
                ],
            },
            {
                "category_id": 2,
                "category_code": CategoryCode.IT_DIGITAL,
                "category_name": "IT/디지털",
                "parent_id": None,
                "sort_order": 2,
                "children": [
                    {
                        "category_id": 5,
                        "category_code": None,
                        "category_name": "인공지능",
                        "parent_id": 2,
                        "sort_order": 1,
                        "children": [],
                    },
                ],
            },
        ],
    }

    repository_mock.find_all_active.assert_called_once_with()


def test_list_categories_excludes_third_level_category(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """3단계 카테고리를 응답에서 제외하고 경고를 기록한다."""

    categories = [
        make_category(
            category_id=1,
            category_name="게임",
            sort_order=1,
        ),
        make_category(
            category_id=2,
            category_name="PC 게임",
            parent_id=1,
            sort_order=1,
        ),
        make_category(
            category_id=3,
            category_name="스팀 게임",
            parent_id=2,
            sort_order=1,
        ),
    ]

    service, _ = make_service(categories)

    with caplog.at_level(
        logging.WARNING,
        logger="app.services.category_service",
    ):
        result = service.list_categories()

    assert result.model_dump() == {
        "categories": [
            {
                "category_id": 1,
                "category_code": None,
                "category_name": "게임",
                "parent_id": None,
                "sort_order": 1,
                "children": [
                    {
                        "category_id": 2,
                        "category_code": None,
                        "category_name": "PC 게임",
                        "parent_id": 1,
                        "sort_order": 1,
                        "children": [],
                    }
                ],
            }
        ],
    }

    assert (
        "활성 세부분류의 유효한 상위 대분류를 찾을 수 없습니다"
        in caplog.text
    )
    assert "parent_id=2" in caplog.text
    assert "child_count=1" in caplog.text


def test_list_categories_excludes_child_without_active_parent(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """활성 부모 목록에 없는 자식을 응답에서 제외한다."""

    categories = [
        make_category(
            category_id=10,
            category_name="부모 없는 세부분류",
            parent_id=999,
            sort_order=1,
        ),
    ]

    service, _ = make_service(categories)

    with caplog.at_level(
        logging.WARNING,
        logger="app.services.category_service",
    ):
        result = service.list_categories()

    assert result.model_dump() == {
        "categories": [],
    }
    assert "parent_id=999" in caplog.text