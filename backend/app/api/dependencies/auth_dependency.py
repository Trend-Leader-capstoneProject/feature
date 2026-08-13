from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from app.api.dependencies.db_dependency import DbSessionDep
from app.core.exceptions import UnauthorizedException
from app.core.security import decode_access_token
from app.models.db_enums import UserStatus
from app.models.user import User
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
)

AccessTokenDep = Annotated[
    str,
    Depends(oauth2_scheme),
]


def get_user_repository(
    db: DbSessionDep,
) -> UserRepository:
    """요청 단위 UserRepository를 생성한다."""

    return UserRepository(
        db=db,
    )


UserRepositoryDep = Annotated[
    UserRepository,
    Depends(get_user_repository),
]


def _extract_user_id_from_token(
    token: str,
) -> int:
    """Access Token을 검증하고 subject에서 사용자 ID를 반환한다."""

    try:
        payload = decode_access_token(
            token,
        )

    except JWTError as exc:
        raise UnauthorizedException() from exc

    subject = payload.get(
        "sub",
    )

    if not isinstance(
        subject,
        str,
    ):
        raise UnauthorizedException()

    try:
        user_id = int(
            subject,
        )

    except ValueError as exc:
        raise UnauthorizedException() from exc

    if user_id <= 0:
        raise UnauthorizedException()

    return user_id


def get_current_user(
    token: AccessTokenDep,
    user_repository: UserRepositoryDep,
) -> User:
    """Bearer Access Token을 기반으로 현재 인증된 사용자를 반환한다."""

    user_id = _extract_user_id_from_token(
        token,
    )

    user = user_repository.find_by_id(
        user_id,
    )

    if user is None:
        raise UnauthorizedException()

    if user.status != UserStatus.ACTIVE:
        raise UnauthorizedException()

    return user


CurrentUserDep = Annotated[
    User,
    Depends(get_current_user),
]
