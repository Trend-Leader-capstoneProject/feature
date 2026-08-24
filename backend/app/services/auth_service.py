from sqlalchemy.orm import Session

from app.core.exceptions import UnauthorizedException
from app.core.security import create_access_token, verify_password
from app.models.db_enums import UserStatus
from app.models.user import User
from app.repositories.interest_repository import InterestRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth_schema import LoginData, LoginRequest, LoginUserData, SessionData

INVALID_LOGIN_MESSAGE = "아이디 또는 비밀번호가 올바르지 않습니다."


class AuthService:
    """일반 로그인 및 인증 세션 비즈니스 로직을 담당하는 Service."""

    def __init__(
        self,
        db: Session,
        user_repository: UserRepository,
        interest_repository: InterestRepository,
    ) -> None:
        self.db = db
        self.user_repository = user_repository
        self.interest_repository = interest_repository

    def login(
        self,
        login_request: LoginRequest,
    ) -> LoginData:
        """로그인 정보를 검증하고 Access Token과 사용자 정보를 반환한다."""

        user = self.user_repository.find_by_login_id(
            login_request.login_id,
        )

        if user is None or user.password_hash is None:
            raise UnauthorizedException(
                message=INVALID_LOGIN_MESSAGE,
            )

        password = login_request.password.get_secret_value()

        if not verify_password(
            password,
            user.password_hash,
        ):
            raise UnauthorizedException(
                message=INVALID_LOGIN_MESSAGE,
            )

        if user.status != UserStatus.ACTIVE:
            raise UnauthorizedException(
                message=INVALID_LOGIN_MESSAGE,
            )

        if user.login_id is None:
            raise UnauthorizedException(
                message=INVALID_LOGIN_MESSAGE,
            )

        session = self.get_session(
            user=user,
        )

        access_token = create_access_token(
            user.user_id,
        )

        return LoginData(
            access_token=access_token,
            user=session.user,
            has_selected_interests=session.has_selected_interests,
            next_step=session.next_step,
        )

    def get_session(
        self,
        user: User,
    ) -> SessionData:
        """인증된 사용자의 현재 앱 진입 상태를 반환한다."""

        if user.login_id is None:
            raise UnauthorizedException()

        has_selected_interests = (
            self.interest_repository.exists_by_user_id(
                user.user_id,
            )
        )

        return SessionData(
            user=LoginUserData(
                user_id=user.user_id,
                login_id=user.login_id,
                name=user.name,
                status=user.status,
            ),
            has_selected_interests=has_selected_interests,
            next_step=(
                "MAIN"
                if has_selected_interests
                else "INTEREST_SELECTION"
            ),
        )
