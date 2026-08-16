import pytest
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
    
    