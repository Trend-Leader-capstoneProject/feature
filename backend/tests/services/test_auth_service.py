from typing import cast
from unittest.mock import Mock

import pytest
from pwdlib import PasswordHash
from pydantic import SecretStr
from pymysql.err import IntegrityError as PyMySQLIntegrityError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ConflictException,
    UnauthorizedException,
)
from app.core.security import (
    decode_access_token,
    verify_password,
)
from app.models.db_enums import UserStatus
from app.models.user import User
from app.repositories.interest_repository import InterestRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth_schema import (
    LoginRequest,
    SignupConflictData,
    SignupRequest,
)
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

    db_mock = Mock(
        spec=Session,
    )

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
        db=cast(
            Session,
            db_mock,
        ),
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


def make_signup_service() -> tuple[
    AuthService,
    Mock,
    Mock,
    Mock,
]:
    """회원가입 테스트용 Mock 의존성을 사용하는 AuthService를 생성한다."""

    db_mock = Mock(
        spec=Session,
    )
    user_repository_mock = Mock(
        spec=UserRepository,
    )
    interest_repository_mock = Mock(
        spec=InterestRepository,
    )

    user_repository_mock.find_by_login_id.return_value = None
    user_repository_mock.find_by_email.return_value = None
    interest_repository_mock.exists_by_user_id.return_value = False

    def save_user(
        user: User,
    ) -> User:
        user.user_id = 200
        return user

    user_repository_mock.save.side_effect = save_user

    service = AuthService(
        db=cast(
            Session,
            db_mock,
        ),
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
        db_mock,
        user_repository_mock,
        interest_repository_mock,
    )


def make_signup_request(
    *,
    email: str | None = "signup@example.com",
) -> SignupRequest:
    """AuthService 테스트용 회원가입 요청을 생성한다."""

    return SignupRequest.model_validate(
        {
            "login_id": "signup_user",
            "password": "signup-password",
            "password_confirm": "signup-password",
            "name": "회원가입 테스트 사용자",
            "email": email,
        }
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


def test_signup_creates_active_user_and_returns_session() -> None:
    """정상 회원가입은 ACTIVE 사용자를 생성하고 인증 세션을 반환한다."""

    (
        service,
        db_mock,
        user_repository_mock,
        interest_repository_mock,
    ) = make_signup_service()

    result = service.signup(
        signup_request=make_signup_request(),
    )

    user_repository_mock.find_by_login_id.assert_called_once_with(
        "signup_user",
    )
    user_repository_mock.find_by_email.assert_called_once_with(
        "signup@example.com",
    )
    user_repository_mock.save.assert_called_once()

    saved_user = user_repository_mock.save.call_args.args[0]

    assert isinstance(
        saved_user,
        User,
    )
    assert saved_user.login_id == "signup_user"
    assert saved_user.name == "회원가입 테스트 사용자"
    assert saved_user.email == "signup@example.com"
    assert saved_user.status == UserStatus.ACTIVE

    assert saved_user.password_hash is not None
    assert saved_user.password_hash != "signup-password"
    assert verify_password(
        "signup-password",
        saved_user.password_hash,
    ) is True

    db_mock.commit.assert_called_once_with()
    db_mock.rollback.assert_not_called()

    interest_repository_mock.exists_by_user_id.assert_called_once_with(
        200,
    )

    assert result.token_type == "Bearer"
    assert result.user.user_id == 200
    assert result.user.login_id == "signup_user"
    assert result.user.name == "회원가입 테스트 사용자"
    assert result.user.status == UserStatus.ACTIVE
    assert result.has_selected_interests is False
    assert result.next_step == "INTEREST_SELECTION"

    payload = decode_access_token(
        result.access_token,
    )

    assert payload["sub"] == "200"


def test_signup_allows_email_none() -> None:
    """이메일을 입력하지 않은 회원가입은 email을 None으로 저장한다."""

    (
        service,
        db_mock,
        user_repository_mock,
        _interest_repository_mock,
    ) = make_signup_service()

    service.signup(
        signup_request=make_signup_request(
            email=None,
        ),
    )

    user_repository_mock.find_by_email.assert_not_called()

    saved_user = user_repository_mock.save.call_args.args[0]

    assert saved_user.email is None

    db_mock.commit.assert_called_once_with()
    db_mock.rollback.assert_not_called()


def test_signup_rejects_duplicated_login_id() -> None:
    """이미 존재하는 로그인 ID는 회원가입 전에 409 충돌로 거부한다."""

    (
        service,
        db_mock,
        user_repository_mock,
        interest_repository_mock,
    ) = make_signup_service()

    user_repository_mock.find_by_login_id.return_value = User(
        user_id=10,
        login_id="signup_user",
        name="기존 사용자",
        status=UserStatus.WITHDRAWN,
    )

    with pytest.raises(
        ConflictException,
    ) as exc_info:
        service.signup(
            signup_request=make_signup_request(),
        )

    assert exc_info.value.status_code == 409

    error_data = exc_info.value.data

    assert isinstance(
        error_data,
        SignupConflictData,
    )
    assert error_data.field == "login_id"
    assert error_data.reason == "DUPLICATED_LOGIN_ID"

    user_repository_mock.find_by_email.assert_not_called()
    user_repository_mock.save.assert_not_called()
    interest_repository_mock.exists_by_user_id.assert_not_called()

    db_mock.commit.assert_not_called()
    db_mock.rollback.assert_not_called()


def test_signup_rejects_duplicated_email() -> None:
    """이미 존재하는 이메일은 409 충돌로 거부한다."""

    (
        service,
        db_mock,
        user_repository_mock,
        interest_repository_mock,
    ) = make_signup_service()

    user_repository_mock.find_by_email.return_value = User(
        user_id=20,
        login_id="existing_user",
        name="기존 이메일 사용자",
        email="signup@example.com",
        status=UserStatus.SUSPENDED,
    )

    with pytest.raises(
        ConflictException,
    ) as exc_info:
        service.signup(
            signup_request=make_signup_request(),
        )

    assert exc_info.value.status_code == 409

    error_data = exc_info.value.data

    assert isinstance(
        error_data,
        SignupConflictData,
    )
    assert error_data.field == "email"
    assert error_data.reason == "DUPLICATED_EMAIL"

    user_repository_mock.save.assert_not_called()
    interest_repository_mock.exists_by_user_id.assert_not_called()

    db_mock.commit.assert_not_called()
    db_mock.rollback.assert_not_called()


def test_signup_rolls_back_when_save_fails() -> None:
    """사용자 저장 중 DB 오류가 발생하면 Transaction을 rollback한다."""

    (
        service,
        db_mock,
        user_repository_mock,
        interest_repository_mock,
    ) = make_signup_service()

    user_repository_mock.save.side_effect = SQLAlchemyError(
        "save failed",
    )

    with pytest.raises(
        SQLAlchemyError,
    ):
        service.signup(
            signup_request=make_signup_request(),
        )

    db_mock.commit.assert_not_called()
    db_mock.rollback.assert_called_once_with()

    interest_repository_mock.exists_by_user_id.assert_not_called()


def test_signup_rolls_back_when_commit_fails() -> None:
    """Commit 중 DB 오류가 발생하면 Transaction을 rollback한다."""

    (
        service,
        db_mock,
        _user_repository_mock,
        interest_repository_mock,
    ) = make_signup_service()

    db_mock.commit.side_effect = SQLAlchemyError(
        "commit failed",
    )

    with pytest.raises(
        SQLAlchemyError,
    ):
        service.signup(
            signup_request=make_signup_request(),
        )

    db_mock.commit.assert_called_once_with()
    db_mock.rollback.assert_called_once_with()

    interest_repository_mock.exists_by_user_id.assert_not_called()


def make_integrity_error(
    *,
    error_code: int,
    message: str,
) -> IntegrityError:
    """테스트용 SQLAlchemy/PyMySQL IntegrityError를 생성한다."""

    original_error = PyMySQLIntegrityError(
        error_code,
        message,
    )

    return IntegrityError(
        statement="INSERT INTO users (...) VALUES (...)",
        params={},
        orig=original_error,
    )


def test_signup_maps_login_id_unique_race_to_conflict() -> None:
    """동시 가입으로 login_id UNIQUE가 충돌하면 rollback 후 409로 변환한다."""

    (
        service,
        db_mock,
        user_repository_mock,
        interest_repository_mock,
    ) = make_signup_service()

    integrity_error = make_integrity_error(
        error_code=1062,
        message=(
            "Duplicate entry 'signup_user' "
            "for key 'uq_users_login_id'"
        ),
    )

    user_repository_mock.save.side_effect = integrity_error

    with pytest.raises(
        ConflictException,
    ) as exc_info:
        service.signup(
            signup_request=make_signup_request(),
        )

    error_data = exc_info.value.data

    assert isinstance(
        error_data,
        SignupConflictData,
    )
    assert error_data.field == "login_id"
    assert error_data.reason == "DUPLICATED_LOGIN_ID"

    db_mock.rollback.assert_called_once_with()
    db_mock.commit.assert_not_called()

    interest_repository_mock.exists_by_user_id.assert_not_called()


def test_signup_maps_email_unique_race_to_conflict() -> None:
    """동시 가입으로 email UNIQUE가 충돌하면 rollback 후 409로 변환한다."""

    (
        service,
        db_mock,
        user_repository_mock,
        interest_repository_mock,
    ) = make_signup_service()

    integrity_error = make_integrity_error(
        error_code=1062,
        message=(
            "Duplicate entry 'signup@example.com' "
            "for key 'uq_users_email'"
        ),
    )

    user_repository_mock.save.side_effect = integrity_error

    with pytest.raises(
        ConflictException,
    ) as exc_info:
        service.signup(
            signup_request=make_signup_request(),
        )

    error_data = exc_info.value.data

    assert isinstance(
        error_data,
        SignupConflictData,
    )
    assert error_data.field == "email"
    assert error_data.reason == "DUPLICATED_EMAIL"

    db_mock.rollback.assert_called_once_with()
    db_mock.commit.assert_not_called()

    interest_repository_mock.exists_by_user_id.assert_not_called()


def test_signup_reraises_unknown_unique_integrity_error() -> None:
    """알려지지 않은 UNIQUE 위반은 회원가입 중복 409로 오인하지 않는다."""

    (
        service,
        db_mock,
        user_repository_mock,
        interest_repository_mock,
    ) = make_signup_service()

    integrity_error = make_integrity_error(
        error_code=1062,
        message=(
            "Duplicate entry 'value' "
            "for key 'uq_unknown_constraint'"
        ),
    )

    user_repository_mock.save.side_effect = integrity_error

    with pytest.raises(
        IntegrityError,
    ) as exc_info:
        service.signup(
            signup_request=make_signup_request(),
        )

    assert exc_info.value is integrity_error

    db_mock.rollback.assert_called_once_with()
    db_mock.commit.assert_not_called()

    interest_repository_mock.exists_by_user_id.assert_not_called()


def test_signup_reraises_non_duplicate_integrity_error() -> None:
    """Duplicate가 아닌 IntegrityError는 원래 DB 오류로 전달한다."""

    (
        service,
        db_mock,
        user_repository_mock,
        interest_repository_mock,
    ) = make_signup_service()

    integrity_error = make_integrity_error(
        error_code=1452,
        message="Cannot add or update a child row",
    )

    user_repository_mock.save.side_effect = integrity_error

    with pytest.raises(
        IntegrityError,
    ) as exc_info:
        service.signup(
            signup_request=make_signup_request(),
        )

    assert exc_info.value is integrity_error

    db_mock.rollback.assert_called_once_with()
    db_mock.commit.assert_not_called()

    interest_repository_mock.exists_by_user_id.assert_not_called()
