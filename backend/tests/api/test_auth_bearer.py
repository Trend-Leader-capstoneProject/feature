from collections.abc import Iterator
from typing import cast
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth_dependency import (
    get_user_repository,
)
from app.api.dependencies.interest_dependency import (
    get_interest_service,
)
from app.core.security import create_access_token
from app.main import create_app
from app.models.db_enums import UserStatus
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.interest_schema import InterestCreateData
from app.services.interest_service import InterestService


@pytest.fixture
def active_user() -> User:
    """Bearer 인증 테스트에서 사용할 ACTIVE 사용자를 생성한다."""

    return User(
        user_id=100,
        name="Bearer 인증 테스트 사용자",
        status=UserStatus.ACTIVE,
    )


@pytest.fixture
def user_repository_mock(
    active_user: User,
) -> Mock:
    """현재 사용자를 반환하는 UserRepository Mock을 생성한다."""

    repository_mock = Mock(
        spec=UserRepository,
    )

    repository_mock.find_by_id.return_value = active_user

    return repository_mock


@pytest.fixture
def interest_service_mock() -> Mock:
    """보호 API 호출에 사용할 InterestService Mock을 생성한다."""

    return Mock(
        spec=InterestService,
    )


@pytest.fixture
def client(
    user_repository_mock: Mock,
    interest_service_mock: Mock,
) -> Iterator[TestClient]:
    """실제 Bearer 인증 Dependency를 사용하는 TestClient를 생성한다."""

    application = create_app()

    def override_user_repository() -> UserRepository:
        return cast(
            UserRepository,
            user_repository_mock,
        )

    def override_interest_service() -> InterestService:
        return cast(
            InterestService,
            interest_service_mock,
        )

    application.dependency_overrides[
        get_user_repository
    ] = override_user_repository

    application.dependency_overrides[
        get_interest_service
    ] = override_interest_service

    try:
        with TestClient(application) as test_client:
            yield test_client
    finally:
        application.dependency_overrides.clear()


def test_bearer_header_authenticates_user(
    client: TestClient,
    user_repository_mock: Mock,
    interest_service_mock: Mock,
) -> None:
    """유효한 Bearer JWT로 보호 API에 접근할 수 있다."""

    interest_service_mock.create_interests.return_value = (
        InterestCreateData(
            selected_category_ids=[
                1,
            ],
            selected_count=1,
        )
    )

    access_token = create_access_token(
        user_id=100,
    )

    response = client.post(
        "/api/users/me/interests",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        json={
            "category_ids": [
                1,
            ],
        },
    )

    assert response.status_code == 201

    assert response.json() == {
        "success": True,
        "statusCode": 201,
        "message": "관심사를 저장했습니다.",
        "data": {
            "selected_category_ids": [
                1,
            ],
            "selected_count": 1,
        },
    }

    user_repository_mock.find_by_id.assert_called_once_with(
        100,
    )

    interest_service_mock.create_interests.assert_called_once_with(
        user_id=100,
        category_ids=[
            1,
        ],
    )


def test_bearer_header_rejects_invalid_token(
    client: TestClient,
    user_repository_mock: Mock,
    interest_service_mock: Mock,
) -> None:
    """유효하지 않은 Bearer JWT는 보호 API에서 401로 거부한다."""

    response = client.post(
        "/api/users/me/interests",
        headers={
            "Authorization": "Bearer invalid-token",
        },
        json={
            "category_ids": [
                1,
            ],
        },
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"

    assert response.json() == {
        "success": False,
        "statusCode": 401,
        "message": "로그인이 필요합니다.",
        "data": None,
    }

    user_repository_mock.find_by_id.assert_not_called()
    interest_service_mock.create_interests.assert_not_called()


def test_protected_endpoint_rejects_missing_authorization_header(
    client: TestClient,
    user_repository_mock: Mock,
    interest_service_mock: Mock,
) -> None:
    """Authorization Header가 없으면 보호 API 접근을 거부한다."""

    response = client.post(
        "/api/users/me/interests",
        json={
            "category_ids": [
                1,
            ],
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "success": False,
        "statusCode": 401,
        "message": "로그인이 필요합니다.",
        "data": None,
    }

    user_repository_mock.find_by_id.assert_not_called()
    interest_service_mock.create_interests.assert_not_called()