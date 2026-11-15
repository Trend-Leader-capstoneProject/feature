import re

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, UnauthorizedException
from app.core.nickname import nickname_key
from app.core.security import hash_password, verify_password
from app.models.db_enums import UserStatus
from app.models.user import User
from app.models.user_profile import UserProfile
from app.repositories.interest_repository import InterestRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth_schema import (
    CheckLoginIdData,
    LoginData,
    LoginRequest,
    LoginUserData,
    SessionData,
    SignupConflictData,
    SignupData,
    SignupRequest,
)
from app.services.session_service import SessionService

MARIADB_DUPLICATE_ENTRY_ERROR_CODE = 1062
LOGIN_ID_UNIQUE_CONSTRAINT = "uq_users_login_id"
EMAIL_UNIQUE_CONSTRAINT = "uq_users_email"
DUPLICATE_KEY_PATTERN = re.compile(
    r"for key ['`](?:[^'`]+\.)?(?P<constraint>[^'`]+)['`]"
)
INVALID_LOGIN_MESSAGE = "아이디 또는 비밀번호가 올바르지 않습니다."


class AuthService:
    """가입의 User·Profile·세션 생성과 로그인의 비밀번호 검증을 조정한다."""

    def __init__(
        self,
        db: Session,
        user_repository: UserRepository,
        interest_repository: InterestRepository,
    ) -> None:
        self.db = db
        self.user_repository = user_repository
        self.interest_repository = interest_repository
        self.profiles = ProfileRepository(db)
        self.sessions = SessionService(db)

    def check_login_id(self, login_id: str) -> CheckLoginIdData:
        available = self.user_repository.find_by_login_id(login_id) is None
        return CheckLoginIdData(
            login_id=login_id,
            is_available=available,
            reason=None if available else "DUPLICATED_LOGIN_ID",
        )

    def signup(self, signup_request: SignupRequest) -> SignupData:
        email = str(signup_request.email) if signup_request.email else None
        if self.user_repository.find_by_login_id(signup_request.login_id) is not None:
            self._conflict("login_id", "DUPLICATED_LOGIN_ID")
        if email and self.user_repository.find_by_email(email) is not None:
            self._conflict("email", "DUPLICATED_EMAIL")
        key = nickname_key(signup_request.nickname)
        if self.profiles.find_key(key) is not None:
            self._conflict("nickname", "DUPLICATED_NICKNAME")

        user = User(
            login_id=signup_request.login_id,
            password_hash=hash_password(signup_request.password.get_secret_value()),
            name=signup_request.name,
            email=email,
            status=UserStatus.ACTIVE,
        )
        try:
            saved_user = self.user_repository.save(user)
            self.profiles.add(
                UserProfile(
                    user_id=saved_user.user_id,
                    nickname=signup_request.nickname,
                    nickname_key=key,
                )
            )
            pair = self.sessions.issue(saved_user)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            conflict = self._get_signup_conflict_data(exc)
            if conflict is None:
                raise
            raise ConflictException(data=conflict) from exc
        except SQLAlchemyError:
            self.db.rollback()
            raise
        app_session = self.get_session(saved_user)
        return SignupData(**pair.model_dump(), **app_session.model_dump())

    @staticmethod
    def _conflict(field, reason) -> None:
        raise ConflictException(data=SignupConflictData(field=field, reason=reason))

    def _get_signup_conflict_data(
        self, exc: IntegrityError
    ) -> SignupConflictData | None:
        args = getattr(exc.orig, "args", ())
        if len(args) < 2 or args[0] != MARIADB_DUPLICATE_ENTRY_ERROR_CODE:
            return None
        match = DUPLICATE_KEY_PATTERN.search(str(args[1]))
        if match is None:
            return None
        mapping = {
            LOGIN_ID_UNIQUE_CONSTRAINT: ("login_id", "DUPLICATED_LOGIN_ID"),
            EMAIL_UNIQUE_CONSTRAINT: ("email", "DUPLICATED_EMAIL"),
            "uq_user_profiles_nickname_key": ("nickname", "DUPLICATED_NICKNAME"),
        }
        conflict = mapping.get(match.group("constraint"))
        if conflict is None:
            return None
        return SignupConflictData(field=conflict[0], reason=conflict[1])

    def login(self, login_request: LoginRequest) -> LoginData:
        candidate = self.user_repository.find_by_login_id(login_request.login_id)
        # 사용자 잠금 이후 최신 비밀번호를 검사해 변경 직전 비밀번호 로그인을 막는다.
        user_id = candidate.user_id if candidate is not None else None
        self.sessions.finish_read_phase()
        user = (
            self.sessions.repository.lock_user(user_id) if user_id is not None else None
        )
        if (
            user is None
            or user.password_hash is None
            or user.status != UserStatus.ACTIVE
            or user.login_id is None
            or not verify_password(
                login_request.password.get_secret_value(), user.password_hash
            )
        ):
            raise UnauthorizedException(message=INVALID_LOGIN_MESSAGE)
        pair = self.sessions.issue(user)
        app_session = self.get_session(user)
        self.db.commit()
        return LoginData(**pair.model_dump(), **app_session.model_dump())

    def get_session(self, user: User) -> SessionData:
        if user.login_id is None:
            raise UnauthorizedException(data={"reason": "ACCOUNT_UNAVAILABLE"})
        has_interests = self.interest_repository.exists_by_user_id(user.user_id)
        return SessionData(
            user=LoginUserData(
                user_id=user.user_id,
                login_id=user.login_id,
                name=user.name,
                status=user.status,
            ),
            has_selected_interests=has_interests,
            next_step="MAIN" if has_interests else "INTEREST_SELECTION",
        )
