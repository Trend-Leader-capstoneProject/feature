from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth_dependency import get_current_user
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
)
from app.main import create_app
from app.models.db_enums import UserStatus
from app.models.user import User
from app.schemas.trend_schema import TrendListData
from app.services.personalized_trend_service import (
    PersonalizedTrendService,
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    """인증 사용자를 주입하는 Personalized Router 테스트 Client."""

    application = create_app()

    def override_current_user() -> User:
        return User(
            user_id=15,
            name="맞춤 트렌드 테스트 사용자",
            status=UserStatus.ACTIVE,
        )

    application.dependency_overrides[
        get_current_user
    ] = override_current_user

    try:
        with TestClient(application) as test_client:
            yield test_client
    finally:
        application.dependency_overrides.clear()


def test_personalized_trends_uses_authenticated_user_defaults(
    client: TestClient,
) -> None:
    """인증 사용자 ID와 기본 Query를 Service에 전달한다."""

    result = TrendListData(
        items=[],
        next_cursor=None,
        has_next=False,
    )

    with patch.object(
        PersonalizedTrendService,
        "list_personalized_trends",
        return_value=result,
    ) as list_personalized_trends:
        response = client.get(
            "/api/trends/personalized",
        )

    assert response.status_code == 200

    assert response.json() == {
        "success": True,
        "statusCode": 200,
        "message": "맞춤 트렌드를 조회했습니다.",
        "data": {
            "items": [],
            "next_cursor": None,
            "has_next": False,
        },
    }

    list_personalized_trends.assert_called_once_with(
        user_id=15,
        limit=20,
        cursor=None,
    )


def test_personalized_trends_requires_bearer_credentials() -> None:
    """실제 Bearer 인증이 없는 요청은 401로 거부한다."""

    application = create_app()

    with patch.object(
        PersonalizedTrendService,
        "list_personalized_trends",
    ) as list_personalized_trends:
        with TestClient(application) as client:
            response = client.get(
                "/api/trends/personalized",
            )

    assert response.status_code == 401

    assert response.headers["www-authenticate"] == "Bearer"

    assert response.json() == {
        "success": False,
        "statusCode": 401,
        "message": "로그인이 필요합니다.",
        "data": None,
    }

    list_personalized_trends.assert_not_called()


def test_personalized_trends_forwards_valid_query_parameters(
    client: TestClient,
) -> None:
    """유효한 limit과 cursor를 변경 없이 Service에 전달한다."""

    result = TrendListData(
        items=[],
        next_cursor=None,
        has_next=False,
    )

    with patch.object(
        PersonalizedTrendService,
        "list_personalized_trends",
        return_value=result,
    ) as list_personalized_trends:
        response = client.get(
            "/api/trends/personalized",
            params={
                "limit": 7,
                "cursor": "sample-cursor",
            },
        )

    assert response.status_code == 200

    list_personalized_trends.assert_called_once_with(
        user_id=15,
        limit=7,
        cursor="sample-cursor",
    )


@pytest.mark.parametrize(
    "limit",
    [
        0,
        51,
        "invalid",
    ],
)
def test_personalized_trends_rejects_invalid_limit(
    client: TestClient,
    limit: int | str,
) -> None:
    """잘못된 limit은 Service 호출 이전에 422로 거부한다."""

    with patch.object(
        PersonalizedTrendService,
        "list_personalized_trends",
    ) as list_personalized_trends:
        response = client.get(
            "/api/trends/personalized",
            params={
                "limit": limit,
            },
        )

    assert response.status_code == 422

    body = response.json()

    assert body["success"] is False
    assert body["statusCode"] == 422
    assert (
        body["message"]
        == "요청 데이터가 올바르지 않습니다."
    )

    list_personalized_trends.assert_not_called()


@pytest.mark.parametrize(
    "limit",
    [
        1,
        50,
    ],
)
def test_personalized_trends_accepts_limit_boundaries(
    client: TestClient,
    limit: int,
) -> None:
    """limit 허용 범위의 양 끝값은 정상 처리한다."""

    result = TrendListData(
        items=[],
        next_cursor=None,
        has_next=False,
    )

    with patch.object(
        PersonalizedTrendService,
        "list_personalized_trends",
        return_value=result,
    ) as list_personalized_trends:
        response = client.get(
            "/api/trends/personalized",
            params={
                "limit": limit,
            },
        )

    assert response.status_code == 200

    list_personalized_trends.assert_called_once_with(
        user_id=15,
        limit=limit,
        cursor=None,
    )


def test_personalized_trends_returns_invalid_cursor_response(
    client: TestClient,
) -> None:
    """Service의 INVALID_CURSOR 오류를 HTTP 400으로 반환한다."""

    with patch.object(
        PersonalizedTrendService,
        "list_personalized_trends",
        side_effect=BadRequestException(
            message="페이지 정보가 올바르지 않습니다.",
            data={
                "reason": "INVALID_CURSOR",
            },
        ),
    ) as list_personalized_trends:
        response = client.get(
            "/api/trends/personalized",
            params={
                "cursor": "invalid-cursor",
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

    list_personalized_trends.assert_called_once_with(
        user_id=15,
        limit=20,
        cursor="invalid-cursor",
    )


@pytest.mark.parametrize(
    ("message", "reason"),
    [
        (
            "저장된 관심사가 없습니다.",
            "INTERESTS_NOT_INITIALIZED",
        ),
        (
            "현재 관심사로 맞춤 트렌드를 조회할 수 없습니다.",
            "INTERESTS_NOT_AVAILABLE",
        ),
    ],
)
def test_personalized_trends_returns_interest_conflict_response(
    client: TestClient,
    message: str,
    reason: str,
) -> None:
    """관심사 상태 충돌을 reason이 포함된 HTTP 409로 반환한다."""

    with patch.object(
        PersonalizedTrendService,
        "list_personalized_trends",
        side_effect=ConflictException(
            message=message,
            data={
                "reason": reason,
            },
        ),
    ) as list_personalized_trends:
        response = client.get(
            "/api/trends/personalized",
        )

    assert response.status_code == 409

    assert response.json() == {
        "success": False,
        "statusCode": 409,
        "message": message,
        "data": {
            "reason": reason,
        },
    }

    list_personalized_trends.assert_called_once_with(
        user_id=15,
        limit=20,
        cursor=None,
    )
