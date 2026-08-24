from typing import Annotated

from fastapi import Depends
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from jose import JWTError

from app.api.dependencies.db_dependency import DbSessionDep
from app.api.dependencies.interest_dependency import InterestRepositoryDep
from app.core.exceptions import UnauthorizedException
from app.core.security import decode_access_token
from app.models.db_enums import UserStatus
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService

bearer_scheme = HTTPBearer(
    bearerFormat="JWT",
    scheme_name="BearerAuth",
    description=(
        "POST /api/auth/login에서 발급받은 "
        "JWT Access Token을 입력합니다."
    ),
)

BearerCredentialsDep = Annotated[
    HTTPAuthorizationCredentials,
    Depends(bearer_scheme),
]


def get_access_token(
    credentials: BearerCredentialsDep,
) -> str:
    """Authorization Bearer Header에서 Access Token을 추출한다."""

    return credentials.credentials


AccessTokenDep = Annotated[
    str,
    Depends(get_access_token),
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


def get_auth_service(
    db: DbSessionDep,
    user_repository: UserRepositoryDep,
    interest_repository: InterestRepositoryDep,
) -> AuthService:
    """인증에 필요한 의존성을 조립해 AuthService를 생성한다."""

    return AuthService(
        db=db,
        user_repository=user_repository,
        interest_repository=interest_repository,
    )


AuthServiceDep = Annotated[
    AuthService,
    Depends(get_auth_service),
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
