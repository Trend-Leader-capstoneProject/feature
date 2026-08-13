from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from jose import JWTError, jwt
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    verify_password,
)

settings = get_settings()

_password_hasher = PasswordHash.recommended()


@pytest.fixture(scope="module")
def password_hash() -> str:
    """비밀번호 검증 테스트에 사용할 Argon2 해시를 생성한다."""

    return _password_hasher.hash(
        "correct-password",
    )


def test_verify_password_returns_true_for_matching_password(
    password_hash: str,
) -> None:
    """평문 비밀번호와 저장된 해시가 일치하면 True를 반환한다."""

    result = verify_password(
        "correct-password",
        password_hash,
    )

    assert result is True


def test_verify_password_returns_false_for_wrong_password(
    password_hash: str,
) -> None:
    """평문 비밀번호와 저장된 해시가 일치하지 않으면 False를 반환한다."""

    result = verify_password(
        "wrong-password",
        password_hash,
    )

    assert result is False


def test_verify_password_returns_false_for_unknown_hash() -> None:
    """인식할 수 없는 비밀번호 해시는 인증 실패로 처리한다."""

    result = verify_password(
        "correct-password",
        "not-a-valid-password-hash",
    )

    assert result is False


def test_create_access_token_contains_subject_and_expiration() -> None:
    """생성된 Access Token에 사용자 ID와 만료 시간이 포함된다."""

    issued_before = datetime.now(UTC)

    token = create_access_token(
        user_id=10,
    )

    issued_after = datetime.now(UTC)

    payload = decode_access_token(
        token,
    )

    assert payload["sub"] == "10"

    expiration = payload["exp"]

    assert isinstance(
        expiration,
        int,
    )

    expire_seconds = settings.access_token_expire_minutes * 60

    assert (
        int(issued_before.timestamp()) + expire_seconds - 1
        <= expiration
        <= int(issued_after.timestamp()) + expire_seconds + 1
    )


@pytest.mark.parametrize(
    "user_id",
    [
        0,
        -1,
    ],
)
def test_create_access_token_rejects_non_positive_user_id(
    user_id: int,
) -> None:
    """양의 정수가 아닌 사용자 ID로는 Access Token을 생성하지 않는다."""

    with pytest.raises(
        ValueError,
        match=r"user_id는 양의 정수여야 합니다\.",
    ):
        create_access_token(
            user_id=user_id,
        )


def test_decode_access_token_rejects_expired_token() -> None:
    """만료된 Access Token을 거부한다."""

    token = jwt.encode(
        {
            "sub": "10",
            "exp": datetime.now(UTC) - timedelta(seconds=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(
        JWTError,
    ):
        decode_access_token(
            token,
        )


def test_decode_access_token_rejects_token_without_expiration() -> None:
    """만료 시간이 없는 Access Token을 거부한다."""

    token = jwt.encode(
        {
            "sub": "10",
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(
        JWTError,
    ):
        decode_access_token(
            token,
        )


def test_decode_access_token_rejects_token_without_subject() -> None:
    """subject가 없는 Access Token을 거부한다."""

    token = jwt.encode(
        {
            "exp": datetime.now(UTC) + timedelta(minutes=10),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(
        JWTError,
    ):
        decode_access_token(
            token,
        )


def test_decode_access_token_rejects_invalid_signature() -> None:
    """다른 Secret Key로 서명된 Access Token을 거부한다."""

    payload: dict[str, Any] = {
        "sub": "10",
        "exp": datetime.now(UTC) + timedelta(minutes=10),
    }

    token = jwt.encode(
        payload,
        "invalid-secret-key-that-is-long-enough",
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(
        JWTError,
    ):
        decode_access_token(
            token,
        )