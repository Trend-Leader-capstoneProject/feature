from collections.abc import Iterator
from typing import cast
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth_dependency import get_current_user
from app.api.dependencies.interest_dependency import get_interest_service
from app.core.exceptions import ConflictException, UnauthorizedException
from app.main import create_app
from app.models.db_enums import UserStatus
from app.models.user import User
from app.schemas.interest_schema import InterestCreateData
from app.services.interest_service import InterestService


@pytest.fixture
def current_user() -> User:
    """Router 테스트에서 사용할 인증 사용자를 생성한다."""

    return User(
        user_id=100,
        name="관심사 Router 테스트 사용자",
        status=UserStatus.ACTIVE,
    )


@pytest.fixture
def interest_service_mock() -> Mock:
    """Router 테스트용 InterestService Mock을 생성한다."""

    return Mock(
        spec=InterestService,
    )


@pytest.fixture
def client(
    current_user: User,
    interest_service_mock: Mock,
) -> Iterator[TestClient]:
    """인증 사용자와 Mock Service를 사용하는 TestClient를 생성한다."""

    application = create_app()

    def override_current_user() -> User:
        return current_user

    def override_interest_service() -> InterestService:
        return cast(
            InterestService,
            interest_service_mock,
        )

    application.dependency_overrides[
        get_current_user
    ] = override_current_user

    application.dependency_overrides[
        get_interest_service
    ] = override_interest_service

    try:
        with TestClient(application) as test_client:
            yield test_client
    finally:
        application.dependency_overrides.clear()


def test_create_interests_returns_created_response(
    client: TestClient,
    interest_service_mock: Mock,
) -> None:
    """관심사 최초 저장 성공 시 201 공통 응답을 반환한다."""

    interest_service_mock.create_interests.return_value = (
        InterestCreateData(
            selected_category_ids=[
                1,
                2,
            ],
            selected_count=2,
        )
    )

    response = client.post(
        "/api/users/me/interests",
        json={
            "category_ids": [
                1,
                2,
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
                2,
            ],
            "selected_count": 2,
        },
    }

    interest_service_mock.create_interests.assert_called_once_with(
        user_id=100,
        category_ids=[
            1,
            2,
        ],
    )


def test_create_interests_returns_422_for_empty_category_ids(
    client: TestClient,
    interest_service_mock: Mock,
) -> None:
    """빈 관심사 배열은 Request Schema에서 거부한다."""

    response = client.post(
        "/api/users/me/interests",
        json={
            "category_ids": [],
        },
    )

    assert response.status_code == 422

    body = response.json()

    assert body["success"] is False
    assert body["statusCode"] == 422
    assert body["message"] == "요청 데이터가 올바르지 않습니다."

    interest_service_mock.create_interests.assert_not_called()


def test_create_interests_returns_422_for_duplicate_category_ids(
    client: TestClient,
    interest_service_mock: Mock,
) -> None:
    """중복 관심사 ID는 Request Schema에서 거부한다."""

    response = client.post(
        "/api/users/me/interests",
        json={
            "category_ids": [
                1,
                1,
            ],
        },
    )

    assert response.status_code == 422

    body = response.json()

    assert body["success"] is False
    assert body["statusCode"] == 422
    assert body["message"] == "요청 데이터가 올바르지 않습니다."

    interest_service_mock.create_interests.assert_not_called()


def test_create_interests_returns_conflict_response(
    client: TestClient,
    interest_service_mock: Mock,
) -> None:
    """이미 관심사가 존재하면 Service의 409 예외를 반환한다."""

    interest_service_mock.create_interests.side_effect = (
        ConflictException(
            message="이미 관심사가 저장된 사용자입니다.",
        )
    )

    response = client.post(
        "/api/users/me/interests",
        json={
            "category_ids": [
                1,
            ],
        },
    )

    assert response.status_code == 409

    assert response.json() == {
        "success": False,
        "statusCode": 409,
        "message": "이미 관심사가 저장된 사용자입니다.",
        "data": None,
    }


def test_create_interests_returns_401_when_authentication_fails(
    interest_service_mock: Mock,
) -> None:
    """인증에 실패하면 관심사 저장 없이 401을 반환한다."""

    application = create_app()

    def override_current_user() -> User:
        raise UnauthorizedException()

    def override_interest_service() -> InterestService:
        return cast(
            InterestService,
            interest_service_mock,
        )

    application.dependency_overrides[
        get_current_user
    ] = override_current_user

    application.dependency_overrides[
        get_interest_service
    ] = override_interest_service

    try:
        with TestClient(application) as client:
            response = client.post(
                "/api/users/me/interests",
                json={
                    "category_ids": [
                        1,
                    ],
                },
            )
    finally:
        application.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"

    assert response.json() == {
        "success": False,
        "statusCode": 401,
        "message": "로그인이 필요합니다.",
        "data": None,
    }

    interest_service_mock.create_interests.assert_not_called()