from typing import cast
from unittest.mock import Mock

import pytest
from jose import jwt

from app.api.dependencies.auth_dependency import get_current_user
from app.core.config import get_settings
from app.core.exceptions import UnauthorizedException
from app.models.db_enums import UserStatus
from app.models.user import User
from app.repositories.user_repository import UserRepository

settings = get_settings()


def make_access_token(
    subject: str | None,
) -> str:
    """테스트용 JWT Access Token을 생성한다."""

    payload: dict[str, str] = {}

    if subject is not None:
        payload["sub"] = subject

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def make_user_repository_mock(
    user: User | None,
) -> Mock:
    """지정된 사용자를 반환하는 UserRepository Mock을 생성한다."""

    repository_mock = Mock(
        spec=UserRepository,
    )
    repository_mock.find_by_id.return_value = user

    return repository_mock


def test_get_current_user_returns_active_user() -> None:
    """유효한 토큰의 ACTIVE 사용자를 반환한다."""

    user = User(
        user_id=10,
        name="인증 테스트 사용자",
        status=UserStatus.ACTIVE,
    )

    repository_mock = make_user_repository_mock(
        user,
    )

    result = get_current_user(
        token=make_access_token(
            "10",
        ),
        user_repository=cast(
            UserRepository,
            repository_mock,
        ),
    )

    assert result is user

    repository_mock.find_by_id.assert_called_once_with(
        10,
    )


def test_get_current_user_rejects_invalid_token() -> None:
    """JWT 형식 또는 서명이 올바르지 않으면 401을 발생시킨다."""

    repository_mock = make_user_repository_mock(
        None,
    )

    with pytest.raises(
        UnauthorizedException,
    ):
        get_current_user(
            token="invalid-token",
            user_repository=cast(
                UserRepository,
                repository_mock,
            ),
        )

    repository_mock.find_by_id.assert_not_called()


def test_get_current_user_rejects_token_without_subject() -> None:
    """JWT subject가 없으면 401을 발생시킨다."""

    repository_mock = make_user_repository_mock(
        None,
    )

    with pytest.raises(
        UnauthorizedException,
    ):
        get_current_user(
            token=make_access_token(
                None,
            ),
            user_repository=cast(
                UserRepository,
                repository_mock,
            ),
        )

    repository_mock.find_by_id.assert_not_called()


@pytest.mark.parametrize(
    "subject",
    [
        "not-a-number",
        "0",
        "-1",
    ],
)
def test_get_current_user_rejects_invalid_subject(
    subject: str,
) -> None:
    """양의 정수가 아닌 subject를 거부한다."""

    repository_mock = make_user_repository_mock(
        None,
    )

    with pytest.raises(
        UnauthorizedException,
    ):
        get_current_user(
            token=make_access_token(
                subject,
            ),
            user_repository=cast(
                UserRepository,
                repository_mock,
            ),
        )

    repository_mock.find_by_id.assert_not_called()


def test_get_current_user_rejects_missing_user() -> None:
    """토큰 사용자가 DB에 없으면 401을 발생시킨다."""

    repository_mock = make_user_repository_mock(
        None,
    )

    with pytest.raises(
        UnauthorizedException,
    ):
        get_current_user(
            token=make_access_token(
                "10",
            ),
            user_repository=cast(
                UserRepository,
                repository_mock,
            ),
        )

    repository_mock.find_by_id.assert_called_once_with(
        10,
    )


@pytest.mark.parametrize(
    "user_status",
    [
        UserStatus.WITHDRAWN,
        UserStatus.SUSPENDED,
    ],
)
def test_get_current_user_rejects_inactive_user(
    user_status: UserStatus,
) -> None:
    """ACTIVE가 아닌 사용자는 인증된 사용자로 반환하지 않는다."""

    user = User(
        user_id=10,
        name="비활성 인증 테스트 사용자",
        status=user_status,
    )

    repository_mock = make_user_repository_mock(
        user,
    )

    with pytest.raises(
        UnauthorizedException,
    ):
        get_current_user(
            token=make_access_token(
                "10",
            ),
            user_repository=cast(
                UserRepository,
                repository_mock,
            ),
        )

    repository_mock.find_by_id.assert_called_once_with(
        10,
    )