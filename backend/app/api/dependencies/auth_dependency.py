from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.dependencies.db_dependency import DbSessionDep
from app.api.dependencies.interest_dependency import InterestRepositoryDep
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.session_service import AuthContext, SessionService, reject

bearer_scheme = HTTPBearer(
    bearerFormat="JWT",
    scheme_name="BearerAuth",
    auto_error=False,
    description="로그인·회원가입에서 발급받은 JWT Access Token",
)
BearerCredentialsDep = Annotated[
    HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
]


def get_access_token(credentials: BearerCredentialsDep) -> str:
    if credentials is None:
        raise reject("ACCESS_TOKEN_REQUIRED")
    return credentials.credentials


AccessTokenDep = Annotated[str, Depends(get_access_token)]


def get_user_repository(db: DbSessionDep) -> UserRepository:
    return UserRepository(db)


UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]


def get_auth_service(
    db: DbSessionDep,
    user_repository: UserRepositoryDep,
    interest_repository: InterestRepositoryDep,
) -> AuthService:
    return AuthService(db, user_repository, interest_repository)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_session_service(db: DbSessionDep) -> SessionService:
    return SessionService(db)


SessionServiceDep = Annotated[SessionService, Depends(get_session_service)]


def get_auth_context(token: AccessTokenDep, service: SessionServiceDep) -> AuthContext:
    return service.authenticate(token)


AuthContextDep = Annotated[AuthContext, Depends(get_auth_context)]


def get_current_user(context: AuthContextDep) -> User:
    return context.user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
