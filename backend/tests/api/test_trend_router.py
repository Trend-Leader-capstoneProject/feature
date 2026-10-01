from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.trend_schema import TrendListData
from app.services.trend_service import TrendService


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Trend 목록 Router 테스트용 Client를 생성한다."""

    application = create_app()

    with TestClient(application) as test_client:
        yield test_client


def test_list_trends_returns_public_success_response_with_defaults(
    client: TestClient,
) -> None:
    """인증 없이 기본 Query로 Trend 목록을 조회한다."""

    result = TrendListData(
        items=[],
        next_cursor=None,
        has_next=False,
    )

    with patch.object(
        TrendService,
        "list_trends",
        return_value=result,
    ) as list_trends:
        response = client.get(
            "/api/trends",
        )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "statusCode": 200,
        "message": "전체 트렌드를 조회했습니다.",
        "data": {
            "items": [],
            "next_cursor": None,
            "has_next": False,
        },
    }

    list_trends.assert_called_once_with(
        category_id=None,
        limit=20,
        cursor=None,
    )


def test_list_trends_forwards_query_parameters(
    client: TestClient,
) -> None:
    """유효한 Query Parameter를 Service에 그대로 전달한다."""

    result = TrendListData(
        items=[],
        next_cursor=None,
        has_next=False,
    )

    with patch.object(
        TrendService,
        "list_trends",
        return_value=result,
    ) as list_trends:
        response = client.get(
            "/api/trends",
            params={
                "category_id": 12,
                "limit": 7,
                "cursor": "test-cursor",
            },
        )

    assert response.status_code == 200

    list_trends.assert_called_once_with(
        category_id=12,
        limit=7,
        cursor="test-cursor",
    )


@pytest.mark.parametrize(
    "params",
    [
        {
            "limit": 0,
        },
        {
            "limit": 51,
        },
        {
            "limit": "invalid",
        },
        {
            "category_id": 0,
        },
        {
            "category_id": "invalid",
        },
    ],
)
def test_list_trends_returns_422_for_invalid_query(
    client: TestClient,
    params: dict[str, int | str],
) -> None:
    """limit/category_id 형식·범위 오류는 Router에서 422로 거부한다."""

    with patch.object(
        TrendService,
        "list_trends",
    ) as list_trends:
        response = client.get(
            "/api/trends",
            params=params,
        )

    assert response.status_code == 422

    body = response.json()

    assert body["success"] is False
    assert body["statusCode"] == 422
    assert (
        body["message"]
        == "요청 데이터가 올바르지 않습니다."
    )

    list_trends.assert_not_called()


@pytest.mark.parametrize(
    "cursor",
    [
        "",
        "x" * 513,
    ],
)
def test_list_trends_returns_400_for_invalid_cursor(
    client: TestClient,
    cursor: str,
) -> None:
    """Cursor 자체의 오류는 FastAPI 422가 아니라 Service의 400을 사용한다."""

    response = client.get(
        "/api/trends",
        params={
            "cursor": cursor,
        },
    )

    assert response.status_code == 400

    assert response.json() == {
        "success": False,
        "statusCode": 400,
        "message": "페이지 정보가 올바르지 않습니다.",
        "data": {
            "reason": "INVALID_CURSOR",
        },
    }


def test_trend_list_openapi_contract() -> None:
    """전체 Trend 목록의 Public OpenAPI 계약을 검증한다."""

    application = create_app()

    operation = application.openapi()["paths"][
        "/api/trends"
    ][
        "get"
    ]

    assert {
        "200",
        "400",
        "404",
        "422",
        "500",
    }.issubset(
        operation["responses"],
    )

    assert "401" not in operation["responses"]
    assert "403" not in operation["responses"]

    assert operation.get(
        "security",
        [],
    ) == []

    parameters = {
        parameter["name"]: parameter
        for parameter in operation["parameters"]
    }

    assert {
        "cursor",
        "limit",
        "category_id",
    } == set(parameters)

    assert (
        parameters["limit"]["schema"]["default"]
        == 20
    )

    assert "maxLength" not in str(
        parameters["cursor"]["schema"]
    )
