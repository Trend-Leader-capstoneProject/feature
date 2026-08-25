import re

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ConflictException,
    UnauthorizedException,
)
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.db_enums import UserStatus
from app.models.user import User
from app.repositories.interest_repository import InterestRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth_schema import (
    LoginData,
    LoginRequest,
    LoginUserData,
    SessionData,
    SignupConflictData,
    SignupData,
    SignupRequest,
)

MARIADB_DUPLICATE_ENTRY_ERROR_CODE = 1062

LOGIN_ID_UNIQUE_CONSTRAINT = "uq_users_login_id"
EMAIL_UNIQUE_CONSTRAINT = "uq_users_email"

DUPLICATE_KEY_PATTERN = re.compile(
    r"for key ['`](?:[^'`]+\.)?(?P<constraint>[^'`]+)['`]"
)

INVALID_LOGIN_MESSAGE = "아이디 또는 비밀번호가 올바르지 않습니다."


class AuthService:
    """일반 회원가입, 로그인 및 인증 세션 비즈니스 로직을 담당하는 Service."""

    def __init__(
        self,
        db: Session,
        user_repository: UserRepository,
        interest_repository: InterestRepository,
    ) -> None:
        self.db = db
        self.user_repository = user_repository
        self.interest_repository = interest_repository

    def signup(
        self,
        signup_request: SignupRequest,
    ) -> SignupData:
        """회원가입 사용자를 생성하고 Access Token과 세션 정보를 반환한다."""

        existing_user = self.user_repository.find_by_login_id(
            signup_request.login_id,
        )

        if existing_user is not None:
            raise ConflictException(
                data=SignupConflictData(
                    field="login_id",
                    reason="DUPLICATED_LOGIN_ID",
                ),
            )

        email = (
            str(signup_request.email)
            if signup_request.email is not None
            else None
        )

        if email is not None:
            existing_user = self.user_repository.find_by_email(
                email,
            )

            if existing_user is not None:
                raise ConflictException(
                    data=SignupConflictData(
                        field="email",
                        reason="DUPLICATED_EMAIL",
                    ),
                )

        password = signup_request.password.get_secret_value()

        user = User(
            login_id=signup_request.login_id,
            password_hash=hash_password(
                password,
            ),
            name=signup_request.name,
            email=email,
            status=UserStatus.ACTIVE,
        )

        try:
            saved_user = self.user_repository.save(
                user,
            )
            self.db.commit()

        except IntegrityError as exc:
            self.db.rollback()

            conflict_data = self._get_signup_conflict_data(
                exc,
            )

            if conflict_data is None:
                raise

            raise ConflictException(
                data=conflict_data,
            ) from exc

        except SQLAlchemyError:
            self.db.rollback()
            raise

        session = self.get_session(
            user=saved_user,
        )

        access_token = create_access_token(
            saved_user.user_id,
        )

        return SignupData(
            access_token=access_token,
            user=session.user,
            has_selected_interests=session.has_selected_interests,
            next_step=session.next_step,
        )

    def _get_signup_conflict_data(
        self,
        exc: IntegrityError,
    ) -> SignupConflictData | None:
        """알려진 회원가입 UNIQUE 위반을 Conflict 데이터로 변환한다."""

        original_error = exc.orig

        if original_error is None:
            return None

        error_args = getattr(
            original_error,
            "args",
            (),
        )

        if (
            len(error_args) < 2
            or error_args[0] != MARIADB_DUPLICATE_ENTRY_ERROR_CODE
        ):
            return None

        error_message = str(
            error_args[1],
        )

        match = DUPLICATE_KEY_PATTERN.search(
            error_message,
        )

        if match is None:
            return None

        constraint_name = match.group(
            "constraint",
        )

        if constraint_name == LOGIN_ID_UNIQUE_CONSTRAINT:
            return SignupConflictData(
                field="login_id",
                reason="DUPLICATED_LOGIN_ID",
            )

        if constraint_name == EMAIL_UNIQUE_CONSTRAINT:
            return SignupConflictData(
                field="email",
                reason="DUPLICATED_EMAIL",
            )

        return None

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
