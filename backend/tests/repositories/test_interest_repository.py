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
    *,
    name: str = "관심사 Repository 테스트 사용자",
) -> User:
    """관심사 Repository 테스트용 사용자를 생성한다."""

    user = User(
        name=name,
        status=UserStatus.ACTIVE,
    )

    db_session.add(
        user,
    )
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

    db_session.add(
        category,
    )
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
                UserInterestCategory.user_id == user.user_id,
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


def test_find_by_user_id_returns_only_target_user_interests(
    db_session: Session,
) -> None:
    """대상 사용자의 관심사만 category_id 순서대로 반환한다."""

    target_user = create_test_user(
        db_session,
        name="관심사 조회 대상 사용자",
    )
    other_user = create_test_user(
        db_session,
        name="관심사 조회 다른 사용자",
    )

    category_one = create_test_category(
        db_session,
        "Repository 조회 관심사 A",
    )
    category_two = create_test_category(
        db_session,
        "Repository 조회 관심사 B",
    )
    other_category = create_test_category(
        db_session,
        "Repository 조회 다른 사용자 관심사",
    )

    repository = InterestRepository(
        db=db_session,
    )

    repository.save(
        [
            UserInterestCategory(
                user_id=target_user.user_id,
                category_id=category_two.category_id,
            ),
            UserInterestCategory(
                user_id=target_user.user_id,
                category_id=category_one.category_id,
            ),
            UserInterestCategory(
                user_id=other_user.user_id,
                category_id=other_category.category_id,
            ),
        ]
    )

    result = repository.find_by_user_id(
        target_user.user_id,
    )

    assert [
        interest.category_id
        for interest in result
    ] == [
        category_one.category_id,
        category_two.category_id,
    ]


def test_find_by_user_id_returns_empty_list_when_interest_does_not_exist(
    db_session: Session,
) -> None:
    """사용자에게 관심사가 없으면 빈 목록을 반환한다."""

    user = create_test_user(
        db_session,
    )

    repository = InterestRepository(
        db=db_session,
    )

    result = repository.find_by_user_id(
        user.user_id,
    )

    assert result == []


def test_find_by_user_id_for_update_returns_target_user_interests(
    db_session: Session,
) -> None:
    """수정용 조회가 대상 사용자의 관심사를 반환한다."""

    target_user = create_test_user(
        db_session,
        name="관심사 Lock 조회 대상 사용자",
    )
    other_user = create_test_user(
        db_session,
        name="관심사 Lock 조회 다른 사용자",
    )

    category_one = create_test_category(
        db_session,
        "Repository Lock 관심사 A",
    )
    category_two = create_test_category(
        db_session,
        "Repository Lock 관심사 B",
    )
    other_category = create_test_category(
        db_session,
        "Repository Lock 다른 사용자 관심사",
    )

    repository = InterestRepository(
        db=db_session,
    )

    repository.save(
        [
            UserInterestCategory(
                user_id=target_user.user_id,
                category_id=category_two.category_id,
            ),
            UserInterestCategory(
                user_id=target_user.user_id,
                category_id=category_one.category_id,
            ),
            UserInterestCategory(
                user_id=other_user.user_id,
                category_id=other_category.category_id,
            ),
        ]
    )

    result = repository.find_by_user_id_for_update(
        target_user.user_id,
    )

    assert [
        interest.category_id
        for interest in result
    ] == [
        category_one.category_id,
        category_two.category_id,
    ]


def test_delete_removes_only_requested_user_interests(
    db_session: Session,
) -> None:
    """지정한 관심사만 제거하고 나머지 사용자 관심사는 유지한다."""

    target_user = create_test_user(
        db_session,
        name="관심사 삭제 대상 사용자",
    )
    other_user = create_test_user(
        db_session,
        name="관심사 삭제 다른 사용자",
    )

    category_one = create_test_category(
        db_session,
        "Repository 삭제 관심사 A",
    )
    category_two = create_test_category(
        db_session,
        "Repository 삭제 관심사 B",
    )
    other_category = create_test_category(
        db_session,
        "Repository 삭제 다른 사용자 관심사",
    )

    repository = InterestRepository(
        db=db_session,
    )

    target_interest_one = UserInterestCategory(
        user_id=target_user.user_id,
        category_id=category_one.category_id,
    )
    target_interest_two = UserInterestCategory(
        user_id=target_user.user_id,
        category_id=category_two.category_id,
    )
    other_interest = UserInterestCategory(
        user_id=other_user.user_id,
        category_id=other_category.category_id,
    )

    repository.save(
        [
            target_interest_one,
            target_interest_two,
            other_interest,
        ]
    )

    repository.delete(
        [
            target_interest_one,
        ]
    )

    target_result = repository.find_by_user_id(
        target_user.user_id,
    )
    other_result = repository.find_by_user_id(
        other_user.user_id,
    )

    assert [
        interest.category_id
        for interest in target_result
    ] == [
        category_two.category_id,
    ]

    assert [
        interest.category_id
        for interest in other_result
    ] == [
        other_category.category_id,
    ]
