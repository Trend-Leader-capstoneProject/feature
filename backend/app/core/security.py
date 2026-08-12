from datetime import UTC, datetime, timedelta
from typing import Any

from jose import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.config import get_settings

settings = get_settings()

_password_hasher = PasswordHash.recommended()


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    """평문 비밀번호가 저장된 비밀번호 해시와 일치하는지 검증한다."""

    try:
        return _password_hasher.verify(
            password,
            password_hash,
        )

    except UnknownHashError:
        return False


def create_access_token(
    user_id: int,
) -> str:
    """사용자 ID를 subject로 갖는 JWT Access Token을 생성한다."""

    if user_id <= 0:
        raise ValueError(
            "user_id는 양의 정수여야 합니다.",
        )

    expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.access_token_expire_minutes,
    )

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(
    token: str,
) -> dict[str, Any]:
    """JWT Access Token의 서명과 필수 claim을 검증한다."""

    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[
            settings.jwt_algorithm,
        ],
        options={
            "require_exp": True,
            "require_sub": True,
        },
    )
