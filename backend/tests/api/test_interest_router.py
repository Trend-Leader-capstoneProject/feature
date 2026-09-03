from collections.abc import Iterator
from typing import cast
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth_dependency import get_current_user
from app.api.dependencies.interest_dependency import get_interest_service
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
    UnauthorizedException,
)
from app.main import create_app
from app.models.db_enums import UserStatus
from app.models.user import User
from app.schemas.interest_schema import (
    InterestCreateData,
    InterestReadData,
    InterestUpdateData,
)
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


def test_get_interests_returns_current_interests(
    client: TestClient,
    interest_service_mock: Mock,
) -> None:
    """현재 관심사 조회 성공 시 200 공통 응답을 반환한다."""

    interest_service_mock.get_interests.return_value = (
        InterestReadData(
            selected_category_ids=[
                1,
                2,
            ],
            selected_count=2,
        )
    )

    response = client.get(
        "/api/users/me/interests",
    )

    assert response.status_code == 200

    assert response.json() == {
        "success": True,
        "statusCode": 200,
        "message": "관심사를 조회했습니다.",
        "data": {
            "selected_category_ids": [
                1,
                2,
            ],
            "selected_count": 2,
        },
    }

    interest_service_mock.get_interests.assert_called_once_with(
        user_id=100,
    )


def test_get_interests_returns_empty_collection(
    client: TestClient,
    interest_service_mock: Mock,
) -> None:
    """저장된 관심사가 없어도 200과 빈 Collection을 반환한다."""

    interest_service_mock.get_interests.return_value = (
        InterestReadData(
            selected_category_ids=[],
            selected_count=0,
        )
    )

    response = client.get(
        "/api/users/me/interests",
    )

    assert response.status_code == 200

    assert response.json() == {
        "success": True,
        "statusCode": 200,
        "message": "관심사를 조회했습니다.",
        "data": {
            "selected_category_ids": [],
            "selected_count": 0,
        },
    }


def test_update_interests_returns_updated_response(
    client: TestClient,
    interest_service_mock: Mock,
) -> None:
    """관심사 전체 교체 성공 시 200 공통 응답을 반환한다."""

    interest_service_mock.update_interests.return_value = (
        InterestUpdateData(
            selected_category_ids=[
                1,
                3,
            ],
            selected_count=2,
        )
    )

    response = client.put(
        "/api/users/me/interests",
        json={
            "category_ids": [
                1,
                3,
            ],
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "success": True,
        "statusCode": 200,
        "message": "관심사를 수정했습니다.",
        "data": {
            "selected_category_ids": [
                1,
                3,
            ],
            "selected_count": 2,
        },
    }

    interest_service_mock.update_interests.assert_called_once_with(
        user_id=100,
        category_ids=[
            1,
            3,
        ],
    )


@pytest.mark.parametrize(
    "category_ids",
    [
        [],
        [1, 1],
        ["1"],
    ],
)
def test_update_interests_returns_422_for_invalid_category_ids(
    client: TestClient,
    interest_service_mock: Mock,
    category_ids: list[object],
) -> None:
    """PUT Request Schema 위반은 Service 호출 전 422로 거부한다."""

    response = client.put(
        "/api/users/me/interests",
        json={
            "category_ids": category_ids,
        },
    )

    assert response.status_code == 422

    body = response.json()

    assert body["success"] is False
    assert body["statusCode"] == 422
    assert body["message"] == "요청 데이터가 올바르지 않습니다."

    interest_service_mock.update_interests.assert_not_called()


def test_update_interests_returns_bad_request_response(
    client: TestClient,
    interest_service_mock: Mock,
) -> None:
    """비활성 또는 하위 카테고리는 400 응답을 유지한다."""

    interest_service_mock.update_interests.side_effect = (
        BadRequestException(
            message=(
                "활성 상태의 대분류 카테고리만 "
                "관심사로 선택할 수 있습니다."
            ),
            data={
                "inactive_category_ids": [
                    3,
                ],
                "child_category_ids": [],
            },
        )
    )

    response = client.put(
        "/api/users/me/interests",
        json={
            "category_ids": [
                3,
            ],
        },
    )

    assert response.status_code == 400
    assert response.json()["data"] == {
        "inactive_category_ids": [
            3,
        ],
        "child_category_ids": [],
    }


def test_update_interests_returns_not_found_response(
    client: TestClient,
    interest_service_mock: Mock,
) -> None:
    """존재하지 않는 카테고리는 404 응답을 유지한다."""

    interest_service_mock.update_interests.side_effect = (
        NotFoundException(
            message="존재하지 않는 카테고리가 포함되어 있습니다.",
            data={
                "category_ids": [
                    999,
                ],
            },
        )
    )

    response = client.put(
        "/api/users/me/interests",
        json={
            "category_ids": [
                999,
            ],
        },
    )

    assert response.status_code == 404
    assert response.json()["data"] == {
        "category_ids": [
            999,
        ],
    }


def test_update_interests_returns_not_initialized_conflict(
    client: TestClient,
    interest_service_mock: Mock,
) -> None:
    """기존 관심사가 없으면 machine-readable 409를 반환한다."""

    interest_service_mock.update_interests.side_effect = (
        ConflictException(
            message="수정할 기존 관심사가 없습니다.",
            data={
                "reason": "INTERESTS_NOT_INITIALIZED",
            },
        )
    )

    response = client.put(
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
        "message": "수정할 기존 관심사가 없습니다.",
        "data": {
            "reason": "INTERESTS_NOT_INITIALIZED",
        },
    }


@pytest.mark.parametrize(
    (
        "method",
        "json_body",
    ),
    [
        (
            "GET",
            None,
        ),
        (
            "PUT",
            {
                "category_ids": [
                    1,
                ],
            },
        ),
    ],
)


def test_read_and_update_interests_return_401_when_authentication_fails(
    interest_service_mock: Mock,
    method: str,
    json_body: dict[str, object] | None,
) -> None:
    """GET/PUT 보호 API는 인증 실패 시 Service를 실행하지 않는다."""

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
            response = client.request(
                method,
                "/api/users/me/interests",
                json=json_body,
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

    interest_service_mock.get_interests.assert_not_called()
    interest_service_mock.update_interests.assert_not_called()
