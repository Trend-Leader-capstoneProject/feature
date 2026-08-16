from collections.abc import Iterator
from typing import Any, cast
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth_dependency import get_auth_service
from app.core.exceptions import UnauthorizedException
from app.main import create_app
from app.models.db_enums import UserStatus
from app.schemas.auth_schema import (
    LoginData,
    LoginRequest,
    LoginUserData,
)
from app.services.auth_service import AuthService

INVALID_LOGIN_MESSAGE = "아이디 또는 비밀번호가 올바르지 않습니다."

@pytest.fixture
def auth_service_mock() -> Mock:
    """Router 테스트용 AuthService Mock을 생성한다."""
    
    return Mock(
        spec=AuthService,
    )
    

@pytest.fixture
def client(
    auth_service_mock: Mock,
) -> Iterator[TestClient]:
    """Mock AuthService를 사용하는 TestClient를 생성한다."""

    application = create_app()
    
    def override_auth_service() -> AuthService:
        return cast(
            AuthService,
            auth_service_mock,
        )
        
    application.dependency_overrides[
        get_auth_service
    ] = override_auth_service
    
    try:
        with TestClient(application) as test_client:
            yield test_client
    finally:
        application.dependency_overrides.clear()
        
        
def test_login_returns_success_response(
    client: TestClient,
    auth_service_mock: Mock,
) -> None:
    """로그인 성공 시 200 공통 응답과 로그인 데이터를 반환한다."""

    auth_service_mock.login.return_value = LoginData(
        access_token="test-access-token",
        user=LoginUserData(
            user_id=100,
            login_id="trend_user",
            name="로그인 테스트 사용자",
            status=UserStatus.ACTIVE,
        ),
        has_selected_interests=True,
        next_step="MAIN",
    )

    response = client.post(
        "/api/auth/login",
        json={
            "login_id": "trend_user",
            "password": "correct-password",
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "success": True,
        "statusCode": 200,
        "message": "로그인에 성공했습니다.",
        "data": {
            "access_token": "test-access-token",
            "token_type": "Bearer",
            "user": {
                "user_id": 100,
                "login_id": "trend_user",
                "name": "로그인 테스트 사용자",
                "status": "ACTIVE",
            },
            "has_selected_interests": True,
            "next_step": "MAIN",
        },
    }

    auth_service_mock.login.assert_called_once()

    login_request = (
        auth_service_mock.login.call_args.kwargs[
            "login_request"
        ]
    )

    assert isinstance(
        login_request,
        LoginRequest,
    )
    assert login_request.login_id == "trend_user"
    assert (
        login_request.password.get_secret_value()
        == "correct-password"
    )
    

def test_login_returns_401_when_authentication_fails(
    client: TestClient,
    auth_service_mock: Mock,
) -> None:
    """Service에서 인증에 실패하면 401 공통 응답을 반환한다."""

    auth_service_mock.login.side_effect = UnauthorizedException(
        message=INVALID_LOGIN_MESSAGE,
    )

    response = client.post(
        "/api/auth/login",
        json={
            "login_id": "trend_user",
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"

    assert response.json() == {
        "success": False,
        "statusCode": 401,
        "message": INVALID_LOGIN_MESSAGE,
        "data": None,
    }

    auth_service_mock.login.assert_called_once()


@pytest.mark.parametrize(
    "request_body",
    [
        {
            "login_id": "",
            "password": "correct-password",
        },
        {
            "password": "correct-password",
        },
        {
            "login_id": "trend_user",
        },
        {
            "login_id": "a" * 51,
            "password": "correct-password",
        },
    ],
)
def test_login_returns_422_for_invalid_request(
    client: TestClient,
    auth_service_mock: Mock,
    request_body: dict[str, Any],
) -> None:
    """잘못된 로그인 요청은 Request Schema에서 422로 거부한다."""

    response = client.post(
        "/api/auth/login",
        json=request_body,
    )

    assert response.status_code == 422

    body = response.json()

    assert body["success"] is False
    assert body["statusCode"] == 422
    assert body["message"] == "요청 데이터가 올바르지 않습니다."

    auth_service_mock.login.assert_not_called()