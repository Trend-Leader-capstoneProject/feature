import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.db_enums import UserStatus
from app.models.user import User
from app.repositories.user_repository import UserRepository

pytestmark = pytest.mark.integration


def test_find_by_id_returns_matching_user(
    db_session: Session,
) -> None:
    """사용자 ID에 해당하는 사용자를 반환한다."""

    user = User(
        name="UserRepository 통합 테스트 사용자",
        status=UserStatus.ACTIVE,
    )

    db_session.add(
        user,
    )
    db_session.flush()

    repository = UserRepository(
        db=db_session,
    )

    result = repository.find_by_id(
        user.user_id,
    )

    assert result is user


def test_find_by_id_returns_none_when_user_does_not_exist(
    db_session: Session,
) -> None:
    """존재하지 않는 사용자 ID를 조회하면 None을 반환한다."""

    repository = UserRepository(
        db=db_session,
    )

    result = repository.find_by_id(
        -1,
    )

    assert result is None


def test_find_by_login_id_returns_matching_user(
    db_session: Session,
) -> None:
    """로그인 ID에 해당하는 사용자를 반환한다."""

    user = User(
        login_id="repository_login_user",
        password_hash="test-password-hash",
        name="로그인 조회 테스트 사용자",
        status=UserStatus.ACTIVE,
    )

    db_session.add(
        user,
    )
    db_session.flush()

    repository = UserRepository(
        db=db_session,
    )

    result = repository.find_by_login_id(
        "repository_login_user",
    )

    assert result is user


def test_find_by_login_id_returns_none_when_user_does_not_exist(
    db_session: Session,
) -> None:
    """존재하지 않는 로그인 ID를 조회하면 None을 반환한다."""

    repository = UserRepository(
        db=db_session,
    )

    result = repository.find_by_login_id(
        "missing_login_user",
    )

    assert result is None


def test_find_by_email_returns_matching_user(
    db_session: Session,
) -> None:
    """이메일에 해당하는 사용자를 반환한다."""

    user = User(
        login_id="repository_email_user",
        password_hash="test-password-hash",
        name="이메일 조회 테스트 사용자",
        email="repository@example.com",
        status=UserStatus.ACTIVE,
    )

    db_session.add(
        user,
    )
    db_session.flush()

    repository = UserRepository(
        db=db_session,
    )

    result = repository.find_by_email(
        "repository@example.com",
    )

    assert result is user


def test_find_by_email_returns_none_when_user_does_not_exist(
    db_session: Session,
) -> None:
    """존재하지 않는 이메일을 조회하면 None을 반환한다."""

    repository = UserRepository(
        db=db_session,
    )

    result = repository.find_by_email(
        "missing@example.com",
    )

    assert result is None


def test_save_flushes_user_and_assigns_user_id(
    db_session: Session,
) -> None:
    """사용자를 flush하여 DB가 생성한 사용자 ID를 확보한다."""

    repository = UserRepository(
        db=db_session,
    )

    user = User(
        login_id="repository_save_user",
        password_hash="test-password-hash",
        name="사용자 저장 테스트",
        email="repository-save@example.com",
        status=UserStatus.ACTIVE,
    )

    result = repository.save(
        user,
    )

    assert result is user
    assert user.user_id > 0

    stored_user = db_session.get(
        User,
        user.user_id,
    )

    assert stored_user is user


def test_save_rejects_duplicated_login_id(
    db_session: Session,
) -> None:
    """DB UNIQUE 제약이 중복 로그인 ID를 거부한다."""

    repository = UserRepository(
        db=db_session,
    )

    first_user = User(
        login_id="duplicated_login_id",
        password_hash="test-password-hash",
        name="첫 번째 사용자",
        status=UserStatus.ACTIVE,
    )

    repository.save(
        first_user,
    )

    duplicated_user = User(
        login_id="duplicated_login_id",
        password_hash="test-password-hash",
        name="두 번째 사용자",
        status=UserStatus.ACTIVE,
    )

    with pytest.raises(
        IntegrityError,
    ):
        repository.save(
            duplicated_user,
        )


def test_save_rejects_duplicated_email(
    db_session: Session,
) -> None:
    """DB UNIQUE 제약이 중복 이메일을 거부한다."""

    repository = UserRepository(
        db=db_session,
    )

    first_user = User(
        login_id="email_unique_user_1",
        password_hash="test-password-hash",
        name="첫 번째 이메일 사용자",
        email="duplicated@example.com",
        status=UserStatus.ACTIVE,
    )

    repository.save(
        first_user,
    )

    duplicated_user = User(
        login_id="email_unique_user_2",
        password_hash="test-password-hash",
        name="두 번째 이메일 사용자",
        email="duplicated@example.com",
        status=UserStatus.ACTIVE,
    )

    with pytest.raises(
        IntegrityError,
    ):
        repository.save(
            duplicated_user,
        )


def test_save_allows_multiple_users_with_null_email(
    db_session: Session,
) -> None:
    """MariaDB users.email UNIQUE 컬럼에 여러 NULL 값을 저장할 수 있다."""

    repository = UserRepository(
        db=db_session,
    )

    first_user = User(
        login_id="null_email_user_1",
        password_hash="test-password-hash",
        name="NULL 이메일 사용자 1",
        email=None,
        status=UserStatus.ACTIVE,
    )

    second_user = User(
        login_id="null_email_user_2",
        password_hash="test-password-hash",
        name="NULL 이메일 사용자 2",
        email=None,
        status=UserStatus.ACTIVE,
    )

    repository.save(
        first_user,
    )
    repository.save(
        second_user,
    )

    assert first_user.user_id > 0
    assert second_user.user_id > 0
    assert first_user.user_id != second_user.user_id
    assert first_user.email is None
    assert second_user.email is None
