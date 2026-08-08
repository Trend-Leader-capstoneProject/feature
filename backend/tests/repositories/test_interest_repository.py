import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.db_enums import UserStatus
from app.models.user import User
from app.models.user_interest_category import UserInterestCategory
from app.repositories.interest_repository import InterestRepository

pytestmark = pytest.mark.integration


def create_test_user(
    db_session: Session,
) -> User:
    """관심사 Repository 테스트용 사용자를 생성한다."""

    user = User(
        name="관심사 Repository 테스트 사용자",
        status=UserStatus.ACTIVE,
    )

    db_session.add(user)
    db_session.flush()

    return user


def create_test_category(
    db_session: Session,
    category_name: str,
) -> Category:
    """관심사 Repository 테스트용 대분류 카테고리를 생성한다."""

    category = Category(
        category_code=None,
        category_name=category_name,
        sort_order=1,
        is_active=True,
        parent_id=None,
    )

    db_session.add(category)
    db_session.flush()

    return category


def test_exists_by_user_id_returns_false_when_interest_does_not_exist(
    db_session: Session,
) -> None:
    """사용자에게 관심사가 없으면 False를 반환한다."""

    user = create_test_user(
        db_session,
    )

    repository = InterestRepository(
        db=db_session,
    )

    result = repository.exists_by_user_id(
        user.user_id,
    )

    assert result is False


def test_save_stores_multiple_user_interests(
    db_session: Session,
) -> None:
    """여러 사용자 관심사를 현재 Transaction에 저장한다."""

    user = create_test_user(
        db_session,
    )

    category_one = create_test_category(
        db_session,
        "Repository 테스트 관심사 A",
    )
    category_two = create_test_category(
        db_session,
        "Repository 테스트 관심사 B",
    )

    repository = InterestRepository(
        db=db_session,
    )

    user_interests = [
        UserInterestCategory(
            user_id=user.user_id,
            category_id=category_one.category_id,
        ),
        UserInterestCategory(
            user_id=user.user_id,
            category_id=category_two.category_id,
        ),
    ]

    result = repository.save(
        user_interests,
    )

    assert result == user_interests

    stored_interests = list(
        db_session.scalars(
            select(
                UserInterestCategory,
            ).where(
                UserInterestCategory.user_id
                == user.user_id,
            )
        ).all()
    )

    assert {
        interest.category_id
        for interest in stored_interests
    } == {
        category_one.category_id,
        category_two.category_id,
    }


def test_exists_by_user_id_returns_true_after_interest_is_saved(
    db_session: Session,
) -> None:
    """관심사를 저장한 사용자는 존재 여부 조회 시 True를 반환한다."""

    user = create_test_user(
        db_session,
    )

    category = create_test_category(
        db_session,
        "Repository 존재 확인 관심사",
    )

    repository = InterestRepository(
        db=db_session,
    )

    repository.save(
        [
            UserInterestCategory(
                user_id=user.user_id,
                category_id=category.category_id,
            )
        ]
    )

    result = repository.exists_by_user_id(
        user.user_id,
    )

    assert result is True