from collections.abc import Iterator
from typing import Any, cast
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth_dependency import get_auth_service
from app.core.exceptions import (
    ConflictException,
    UnauthorizedException,
)
from app.main import create_app
from app.models.db_enums import UserStatus
from app.schemas.auth_schema import (
    CheckLoginIdData,
    LoginData,
    LoginIdAvailabilityReason,
    LoginRequest,
    LoginUserData,
    SignupConflictData,
    SignupConflictField,
    SignupConflictReason,
    SignupData,
    SignupRequest,
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


def test_signup_returns_created_response(
    client: TestClient,
    auth_service_mock: Mock,
) -> None:
    """회원가입 성공 시 201과 초기 인증 세션을 반환한다."""

    auth_service_mock.signup.return_value = SignupData(
        access_token="signup-access-token",
        user=LoginUserData(
            user_id=200,
            login_id="signup_user",
            name="회원가입 사용자",
            status=UserStatus.ACTIVE,
        ),
        has_selected_interests=False,
        next_step="INTEREST_SELECTION",
    )

    response = client.post(
        "/api/auth/signup",
        json={
            "login_id": "signup_user",
            "password": "signup-password",
            "password_confirm": "signup-password",
            "name": "회원가입 사용자",
            "email": None,
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["success"] is True
    assert body["statusCode"] == 201
    assert body["message"] == "회원가입이 완료되었습니다."
    assert body["data"]["access_token"] == "signup-access-token"
    assert body["data"]["token_type"] == "Bearer"
    assert body["data"]["has_selected_interests"] is False
    assert body["data"]["next_step"] == "INTEREST_SELECTION"

    auth_service_mock.signup.assert_called_once()

    signup_request = (
        auth_service_mock.signup.call_args.kwargs[
            "signup_request"
        ]
    )

    assert isinstance(
        signup_request,
        SignupRequest,
    )
    assert signup_request.login_id == "signup_user"


@pytest.mark.parametrize(
    (
        "is_available",
        "reason",
        "expected_message",
    ),
    [
        (
            True,
            None,
            "사용 가능한 아이디입니다.",
        ),
        (
            False,
            "DUPLICATED_LOGIN_ID",
            "이미 사용 중인 아이디입니다.",
        ),
    ],
)
def test_check_login_id_returns_availability(
    client: TestClient,
    auth_service_mock: Mock,
    is_available: bool,
    reason: LoginIdAvailabilityReason | None,
    expected_message: str,
) -> None:
    """로그인 ID 사용 가능 여부를 200으로 반환한다."""

    auth_service_mock.check_login_id.return_value = CheckLoginIdData(
        login_id="trend_user",
        is_available=is_available,
        reason=reason,
    )

    response = client.get(
        "/api/auth/check-login-id",
        params={
            "login_id": "trend_user",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["statusCode"] == 200
    assert body["message"] == expected_message
    assert body["data"] == {
        "login_id": "trend_user",
        "is_available": is_available,
        "reason": reason,
    }

    auth_service_mock.check_login_id.assert_called_once_with(
        login_id="trend_user",
    )


@pytest.mark.parametrize(
    "login_id",
    [
        "abc",
        "TrendUser",
        "1user",
        "_user",
        "user-name",
        "a" * 51,
    ],
)
def test_check_login_id_returns_422_for_invalid_login_id(
    client: TestClient,
    auth_service_mock: Mock,
    login_id: str,
) -> None:
    """잘못된 로그인 ID Query는 422로 거부한다."""

    response = client.get(
        "/api/auth/check-login-id",
        params={
            "login_id": login_id,
        },
    )

    assert response.status_code == 422

    auth_service_mock.check_login_id.assert_not_called()


def test_check_login_id_returns_422_when_login_id_is_missing(
    client: TestClient,
    auth_service_mock: Mock,
) -> None:
    """login_id Query가 없으면 422로 거부한다."""

    response = client.get(
        "/api/auth/check-login-id",
    )

    assert response.status_code == 422
    auth_service_mock.check_login_id.assert_not_called()


@pytest.mark.parametrize(
    (
        "field",
        "reason",
    ),
    [
        (
            "login_id",
            "DUPLICATED_LOGIN_ID",
        ),
        (
            "email",
            "DUPLICATED_EMAIL",
        ),
    ],
)
def test_signup_returns_409_for_duplicate_conflict(
    client: TestClient,
    auth_service_mock: Mock,
    field: SignupConflictField,
    reason: SignupConflictReason,
) -> None:
    """회원가입 중복 충돌은 machine-readable 409 응답으로 반환한다."""

    auth_service_mock.signup.side_effect = ConflictException(
        data=SignupConflictData.model_validate(
            {
                "field": field,
                "reason": reason,
            }
        ),
    )

    response = client.post(
        "/api/auth/signup",
        json={
            "login_id": "signup_user",
            "password": "signup-password",
            "password_confirm": "signup-password",
            "name": "회원가입 사용자",
            "email": "signup@example.com",
        },
    )

    assert response.status_code == 409

    body = response.json()

    assert body["success"] is False
    assert body["statusCode"] == 409
    assert body["message"] == "이미 존재하는 데이터입니다."
    assert body["data"] == {
        "field": field,
        "reason": reason,
    }

    auth_service_mock.signup.assert_called_once()


@pytest.mark.parametrize(
    "request_body",
    [
        {
            "password": "signup-password",
            "password_confirm": "signup-password",
            "name": "회원가입 사용자",
        },
        {
            "login_id": "Bad-User",
            "password": "signup-password",
            "password_confirm": "signup-password",
            "name": "회원가입 사용자",
        },
        {
            "login_id": "signup_user",
            "password": "a" * 14,
            "password_confirm": "a" * 14,
            "name": "회원가입 사용자",
        },
        {
            "login_id": "signup_user",
            "password": "signup-password",
            "password_confirm": "different-password",
            "name": "회원가입 사용자",
        },
        {
            "login_id": "signup_user",
            "password": "signup-password",
            "password_confirm": "signup-password",
        },
        {
            "login_id": "signup_user",
            "password": "signup-password",
            "password_confirm": "signup-password",
            "name": "회원가입 사용자",
            "email": "not-an-email",
        },
    ],
)
def test_signup_returns_422_for_invalid_request(
    client: TestClient,
    auth_service_mock: Mock,
    request_body: dict[str, Any],
) -> None:
    """잘못된 회원가입 요청은 422로 거부하고 Service를 호출하지 않는다."""

    response = client.post(
        "/api/auth/signup",
        json=request_body,
    )

    assert response.status_code == 422

    body = response.json()

    assert body["success"] is False
    assert body["statusCode"] == 422
    assert body["message"] == "요청 데이터가 올바르지 않습니다."
    assert body["data"]["errors"]

    auth_service_mock.signup.assert_not_called()
