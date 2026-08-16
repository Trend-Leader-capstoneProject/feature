from typing import cast
from unittest.mock import Mock

import pytest
from pwdlib import PasswordHash
from pydantic import SecretStr

from app.core.exceptions import UnauthorizedException
from app.core.security import decode_access_token
from app.models.db_enums import UserStatus
from app.models.user import User
from app.repositories.interest_repository import InterestRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth_schema import LoginRequest
from app.services.auth_service import AuthService

CORRECT_PASSWORD = "correct-password"
INVALID_LOGIN_MESSAGE = "아이디 또는 비밀번호가 올바르지 않습니다."

_password_hasher = PasswordHash.recommended()


@pytest.fixture(scope="module")
def password_hash() -> str:
    """AuthService 테스트에 사용할 Argon2 비밀번호 해시를 생성한다."""

    return _password_hasher.hash(
        CORRECT_PASSWORD,
    )


def make_user(
    password_hash: str | None,
    *,
    login_id: str | None = "trend_user",
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    """AuthService 테스트용 사용자를 생성한다."""

    return User(
        user_id=100,
        login_id=login_id,
        password_hash=password_hash,
        name="로그인 테스트 사용자",
        status=status,
    )


def make_service(
    user: User | None,
    *,
    has_selected_interests: bool = False,
) -> tuple[AuthService, Mock, Mock]:
    """Mock Repository를 사용하는 AuthService를 생성한다."""

    user_repository_mock = Mock(
        spec=UserRepository,
    )
    interest_repository_mock = Mock(
        spec=InterestRepository,
    )

    user_repository_mock.find_by_login_id.return_value = user
    interest_repository_mock.exists_by_user_id.return_value = (
        has_selected_interests
    )

    service = AuthService(
        user_repository=cast(
            UserRepository,
            user_repository_mock,
        ),
        interest_repository=cast(
            InterestRepository,
            interest_repository_mock,
        ),
    )

    return (
        service,
        user_repository_mock,
        interest_repository_mock,
    )


def make_login_request(
    *,
    password: str = CORRECT_PASSWORD,
) -> LoginRequest:
    """AuthService 테스트용 로그인 요청을 생성한다."""

    return LoginRequest(
        login_id="trend_user",
        password=SecretStr(password),
    )


@pytest.mark.parametrize(
    (
        "has_selected_interests",
        "expected_next_step",
    ),
    [
        (
            True,
            "MAIN",
        ),
        (
            False,
            "INTEREST_SELECTION",
        ),
    ],
)
def test_login_returns_access_token_and_user_data(
    password_hash: str,
    has_selected_interests: bool,
    expected_next_step: str,
) -> None:
    """정상 로그인 시 JWT와 사용자 정보를 반환한다."""

    user = make_user(
        password_hash,
    )

    (
        service,
        user_repository_mock,
        interest_repository_mock,
    ) = make_service(
        user,
        has_selected_interests=has_selected_interests,
    )

    result = service.login(
        login_request=make_login_request(),
    )

    assert result.token_type == "Bearer"

    assert result.user.user_id == 100
    assert result.user.login_id == "trend_user"
    assert result.user.name == "로그인 테스트 사용자"
    assert result.user.status == UserStatus.ACTIVE

    assert (
        result.has_selected_interests
        is has_selected_interests
    )
    assert result.next_step == expected_next_step

    payload = decode_access_token(
        result.access_token,
    )

    assert payload["sub"] == "100"
    assert "exp" in payload

    user_repository_mock.find_by_login_id.assert_called_once_with(
        "trend_user",
    )
    interest_repository_mock.exists_by_user_id.assert_called_once_with(
        100,
    )


def test_login_raises_unauthorized_when_user_does_not_exist() -> None:
    """존재하지 않는 로그인 ID는 401 인증 실패로 처리한다."""

    (
        service,
        user_repository_mock,
        interest_repository_mock,
    ) = make_service(
        None,
    )

    with pytest.raises(
        UnauthorizedException,
    ) as exc_info:
        service.login(
            login_request=make_login_request(),
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.message == INVALID_LOGIN_MESSAGE

    user_repository_mock.find_by_login_id.assert_called_once_with(
        "trend_user",
    )
    interest_repository_mock.exists_by_user_id.assert_not_called()


def test_login_raises_unauthorized_when_password_hash_is_none() -> None:
    """비밀번호가 없는 OAuth 전용 사용자는 일반 로그인을 거부한다."""

    user = make_user(
        None,
    )

    (
        service,
        user_repository_mock,
        interest_repository_mock,
    ) = make_service(
        user,
    )

    with pytest.raises(
        UnauthorizedException,
    ) as exc_info:
        service.login(
            login_request=make_login_request(),
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.message == INVALID_LOGIN_MESSAGE

    user_repository_mock.find_by_login_id.assert_called_once_with(
        "trend_user",
    )
    interest_repository_mock.exists_by_user_id.assert_not_called()


def test_login_raises_unauthorized_when_password_is_wrong(
    password_hash: str,
) -> None:
    """비밀번호가 일치하지 않으면 401 인증 실패로 처리한다."""

    user = make_user(
        password_hash,
    )

    (
        service,
        user_repository_mock,
        interest_repository_mock,
    ) = make_service(
        user,
    )

    with pytest.raises(
        UnauthorizedException,
    ) as exc_info:
        service.login(
            login_request=make_login_request(
                password="wrong-password",
            ),
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.message == INVALID_LOGIN_MESSAGE

    user_repository_mock.find_by_login_id.assert_called_once_with(
        "trend_user",
    )
    interest_repository_mock.exists_by_user_id.assert_not_called()


@pytest.mark.parametrize(
    "user_status",
    [
        UserStatus.WITHDRAWN,
        UserStatus.SUSPENDED,
    ],
)
def test_login_raises_unauthorized_when_user_is_not_active(
    password_hash: str,
    user_status: UserStatus,
) -> None:
    """ACTIVE 상태가 아닌 사용자는 로그인을 거부한다."""

    user = make_user(
        password_hash,
        status=user_status,
    )

    (
        service,
        user_repository_mock,
        interest_repository_mock,
    ) = make_service(
        user,
    )

    with pytest.raises(
        UnauthorizedException,
    ) as exc_info:
        service.login(
            login_request=make_login_request(),
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.message == INVALID_LOGIN_MESSAGE

    user_repository_mock.find_by_login_id.assert_called_once_with(
        "trend_user",
    )
    interest_repository_mock.exists_by_user_id.assert_not_called()


def test_login_raises_unauthorized_when_user_login_id_is_none(
    password_hash: str,
) -> None:
    """조회된 사용자의 로그인 ID가 없으면 일반 로그인을 거부한다."""

    user = make_user(
        password_hash,
        login_id=None,
    )

    (
        service,
        user_repository_mock,
        interest_repository_mock,
    ) = make_service(
        user,
    )

    with pytest.raises(
        UnauthorizedException,
    ) as exc_info:
        service.login(
            login_request=make_login_request(),
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.message == INVALID_LOGIN_MESSAGE

    user_repository_mock.find_by_login_id.assert_called_once_with(
        "trend_user",
    )
    interest_repository_mock.exists_by_user_id.assert_not_called()