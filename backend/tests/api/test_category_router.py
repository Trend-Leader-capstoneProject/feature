from collections.abc import Iterator
from typing import cast
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.category_dependency import get_category_service
from app.main import create_app
from app.models.db_enums import CategoryCode
from app.schemas.category_schema import CategoryItem, CategoryListData
from app.services.category_service import CategoryService


@pytest.fixture
def category_service_mock() -> Mock:
    """Router 테스트용 CategoryService Mock을 생성한다."""

    return Mock(
        spec=CategoryService,
    )


@pytest.fixture
def client(
    category_service_mock: Mock,
) -> Iterator[TestClient]:
    """실제 DB 대신 Mock Service를 사용하는 TestClient를 생성한다."""

    application = create_app()

    def override_category_service() -> CategoryService:
        return cast(
            CategoryService,
            category_service_mock,
        )

    application.dependency_overrides[get_category_service] = override_category_service

    try:
        with TestClient(application) as test_client:
            yield test_client
    finally:
        application.dependency_overrides.clear()


def test_list_categories_returns_hierarchical_response(
    client: TestClient,
    category_service_mock: Mock,
) -> None:
    """카테고리 API가 공통 응답과 계층 데이터를 반환한다."""

    category_service_mock.list_categories.return_value = CategoryListData(
        categories=[
            CategoryItem(
                category_id=1,
                category_code=CategoryCode.GAME,
                category_name="게임",
                parent_id=None,
                sort_order=1,
                children=[
                    CategoryItem(
                        category_id=2,
                        category_code=None,
                        category_name="PC 게임",
                        parent_id=1,
                        sort_order=1,
                        children=[],
                    )
                ],
            )
        ]
    )

    response = client.get(
        "/api/categories",
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "statusCode": 200,
        "message": "카테고리 목록을 조회했습니다.",
        "data": {
            "categories": [
                {
                    "category_id": 1,
                    "category_code": "GAME",
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
        },
    }

    category_service_mock.list_categories.assert_called_once_with()


def test_list_categories_returns_empty_array_without_authentication(
    client: TestClient,
    category_service_mock: Mock,
) -> None:
    """인증 헤더 없이 호출해도 빈 카테고리 목록을 반환한다."""

    category_service_mock.list_categories.return_value = CategoryListData(
        categories=[],
    )

    response = client.get(
        "/api/categories",
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "statusCode": 200,
        "message": "카테고리 목록을 조회했습니다.",
        "data": {
            "categories": [],
        },
    }


def test_list_categories_http_status_matches_body_status(
    client: TestClient,
    category_service_mock: Mock,
) -> None:
    """실제 HTTP 상태 코드와 응답 Body의 statusCode가 같은지 확인한다."""

    category_service_mock.list_categories.return_value = CategoryListData(
        categories=[],
    )

    response = client.get(
        "/api/categories",
    )
    body = response.json()

    assert response.status_code == body["statusCode"]
