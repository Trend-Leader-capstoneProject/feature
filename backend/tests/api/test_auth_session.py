from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from jose import jwt

from app.api.dependencies.auth_dependency import (
    get_user_repository,
)
from app.api.dependencies.interest_dependency import (
    get_interest_repository,
)
from app.core.config import get_settings
from app.core.security import create_access_token
from app.main import create_app
from app.models.db_enums import UserStatus
from app.models.user import User
from app.repositories.interest_repository import InterestRepository
from app.repositories.user_repository import UserRepository

settings = get_settings()


def make_user(
    *,
    status: UserStatus = UserStatus.ACTIVE,
    login_id: str | None = "trend_user",
) -> User:
    """Session API 테스트용 사용자를 생성한다."""

    return User(
        user_id=100,
        login_id=login_id,
        name="세션 테스트 사용자",
        status=status,
    )


def make_expired_access_token(
    user_id: int,
) -> str:
    """이미 만료된 테스트용 JWT Access Token을 생성한다."""

    return jwt.encode(
        {
            "sub": str(user_id),
            "exp": datetime.now(UTC)
            - timedelta(
                minutes=1,
            ),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def assert_unauthorized_response(
    response: Response,
) -> None:
    """공통 401 응답 구조를 검증한다."""

    assert response.status_code == 401

    assert response.json() == {
        "success": False,
        "statusCode": 401,
        "message": "로그인이 필요합니다.",
        "data": None,
    }


@pytest.fixture
def user_repository_mock() -> Mock:
    """Session API 테스트용 UserRepository Mock을 생성한다."""

    return Mock(
        spec=UserRepository,
    )


@pytest.fixture
def interest_repository_mock() -> Mock:
    """Session API 테스트용 InterestRepository Mock을 생성한다."""

    return Mock(
        spec=InterestRepository,
    )


@pytest.fixture
def client(
    user_repository_mock: Mock,
    interest_repository_mock: Mock,
) -> Iterator[TestClient]:
    """실제 Auth Dependency와 AuthService를 사용하는 TestClient를 생성한다."""

    application = create_app()

    def override_user_repository() -> UserRepository:
        return cast(
            UserRepository,
            user_repository_mock,
        )

    def override_interest_repository() -> InterestRepository:
        return cast(
            InterestRepository,
            interest_repository_mock,
        )

    application.dependency_overrides[
        get_user_repository
    ] = override_user_repository

    application.dependency_overrides[
        get_interest_repository
    ] = override_interest_repository

    try:
        with TestClient(application) as test_client:
            yield test_client
    finally:
        application.dependency_overrides.clear()


@pytest.mark.parametrize(
    (
        "has_selected_interests",
        "expected_next_step",
    ),
    [
        (
            False,
            "INTEREST_SELECTION",
        ),
        (
            True,
            "MAIN",
        ),
    ],
)
def test_session_returns_current_session(
    client: TestClient,
    user_repository_mock: Mock,
    interest_repository_mock: Mock,
    has_selected_interests: bool,
    expected_next_step: str,
) -> None:
    """유효한 Token은 현재 사용자와 앱 진입 상태를 반환한다."""

    user_repository_mock.find_by_id.return_value = make_user()

    interest_repository_mock.exists_by_user_id.return_value = (
        has_selected_interests
    )

    access_token = create_access_token(
        user_id=100,
    )

    response = client.get(
        "/api/auth/session",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "success": True,
        "statusCode": 200,
        "message": "인증 세션을 확인했습니다.",
        "data": {
            "user": {
                "user_id": 100,
                "login_id": "trend_user",
                "name": "세션 테스트 사용자",
                "status": "ACTIVE",
            },
            "has_selected_interests": has_selected_interests,
            "next_step": expected_next_step,
        },
    }

    user_repository_mock.find_by_id.assert_called_once_with(
        100,
    )

    interest_repository_mock.exists_by_user_id.assert_called_once_with(
        100,
    )


def test_session_rejects_missing_authorization_header(
    client: TestClient,
    user_repository_mock: Mock,
    interest_repository_mock: Mock,
) -> None:
    """Authorization Header가 없으면 Session 조회를 거부한다."""

    response = client.get(
        "/api/auth/session",
    )

    assert_unauthorized_response(
        response,
    )

    user_repository_mock.find_by_id.assert_not_called()
    interest_repository_mock.exists_by_user_id.assert_not_called()


def test_session_rejects_invalid_token(
    client: TestClient,
    user_repository_mock: Mock,
    interest_repository_mock: Mock,
) -> None:
    """유효하지 않은 JWT는 Session 조회를 거부한다."""

    response = client.get(
        "/api/auth/session",
        headers={
            "Authorization": "Bearer invalid-token",
        },
    )

    assert_unauthorized_response(
        response,
    )

    user_repository_mock.find_by_id.assert_not_called()
    interest_repository_mock.exists_by_user_id.assert_not_called()


def test_session_rejects_expired_token(
    client: TestClient,
    user_repository_mock: Mock,
    interest_repository_mock: Mock,
) -> None:
    """만료된 JWT는 Session 조회를 거부한다."""

    response = client.get(
        "/api/auth/session",
        headers={
            "Authorization": (
                f"Bearer {make_expired_access_token(100)}"
            ),
        },
    )

    assert_unauthorized_response(
        response,
    )

    user_repository_mock.find_by_id.assert_not_called()
    interest_repository_mock.exists_by_user_id.assert_not_called()


def test_session_rejects_missing_user(
    client: TestClient,
    user_repository_mock: Mock,
    interest_repository_mock: Mock,
) -> None:
    """Token 사용자가 DB에 존재하지 않으면 Session 조회를 거부한다."""

    user_repository_mock.find_by_id.return_value = None

    access_token = create_access_token(
        user_id=100,
    )

    response = client.get(
        "/api/auth/session",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert_unauthorized_response(
        response,
    )

    user_repository_mock.find_by_id.assert_called_once_with(
        100,
    )
    interest_repository_mock.exists_by_user_id.assert_not_called()


@pytest.mark.parametrize(
    "user_status",
    [
        UserStatus.WITHDRAWN,
        UserStatus.SUSPENDED,
    ],
)
def test_session_rejects_inactive_user(
    client: TestClient,
    user_repository_mock: Mock,
    interest_repository_mock: Mock,
    user_status: UserStatus,
) -> None:
    """ACTIVE가 아닌 사용자의 Session 조회를 거부한다."""

    user_repository_mock.find_by_id.return_value = make_user(
        status=user_status,
    )

    access_token = create_access_token(
        user_id=100,
    )

    response = client.get(
        "/api/auth/session",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert_unauthorized_response(
        response,
    )

    user_repository_mock.find_by_id.assert_called_once_with(
        100,
    )
    interest_repository_mock.exists_by_user_id.assert_not_called()


def test_session_rejects_user_without_login_id(
    client: TestClient,
    user_repository_mock: Mock,
    interest_repository_mock: Mock,
) -> None:
    """현재 Session 계약을 만족하지 않는 사용자를 거부한다."""

    user_repository_mock.find_by_id.return_value = make_user(
        login_id=None,
    )

    access_token = create_access_token(
        user_id=100,
    )

    response = client.get(
        "/api/auth/session",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert_unauthorized_response(
        response,
    )

    user_repository_mock.find_by_id.assert_called_once_with(
        100,
    )
    interest_repository_mock.exists_by_user_id.assert_not_called()