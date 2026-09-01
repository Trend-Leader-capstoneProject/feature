import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.db_enums import UserStatus
from app.models.user import User
from app.models.user_interest_category import UserInterestCategory
from app.repositories.category_repository import CategoryRepository
from app.repositories.interest_repository import InterestRepository
from app.services.interest_service import InterestService

pytestmark = pytest.mark.integration


class FailingSaveInterestRepository(
    InterestRepository,
):
    """
    관심사 추가 단계에서 강제로 DB 오류를 발생시키는 테스트 Repository.
    실제 DB 처리
    """

    def save(
        self,
        user_interests: list[UserInterestCategory],
    ) -> list[UserInterestCategory]:
        raise SQLAlchemyError(
            "관심사 저장 강제 실패",
        )


def create_test_user(
    db_session: Session,
    *,
    name: str,
) -> User:
    """InterestService 통합 테스트용 사용자를 생성한다."""

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
    *,
    category_name: str,
) -> Category:
    """InterestService 통합 테스트용 활성 대분류를 생성한다."""

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


def create_user_interests(
    db_session: Session,
    *,
    user_id: int,
    category_ids: list[int],
) -> list[UserInterestCategory]:
    """테스트용 사용자 관심사 Row를 생성한다."""

    user_interests = [
        UserInterestCategory(
            user_id=user_id,
            category_id=category_id,
        )
        for category_id in category_ids
    ]

    db_session.add_all(
        user_interests,
    )
    db_session.flush()

    return user_interests


def build_service(
    db_session: Session,
    *,
    interest_repository: InterestRepository | None = None,
) -> InterestService:
    """실제 MariaDB Repository를 사용하는 InterestService를 생성한다."""

    return InterestService(
        db=db_session,
        category_repository=CategoryRepository(
            db=db_session,
        ),
        interest_repository=(
            interest_repository
            or InterestRepository(
                db=db_session,
            )
        ),
    )


def find_interest_rows(
    db_session: Session,
    *,
    user_id: int,
) -> list[UserInterestCategory]:
    """사용자의 관심사 Row를 결정적인 순서로 조회한다."""

    statement = (
        select(
            UserInterestCategory,
        )
        .where(
            UserInterestCategory.user_id == user_id,
        )
        .order_by(
            UserInterestCategory.category_id,
        )
    )

    return list(
        db_session.scalars(
            statement,
        ).all()
    )


def test_update_interests_applies_diff_and_preserves_kept_row(
    db_session: Session,
) -> None:
    """실제 DB에서 diff 수정하며 유지 Row를 재생성하지 않는다."""

    user = create_test_user(
        db_session,
        name="Service 통합 수정 사용자",
    )

    category_one = create_test_category(
        db_session,
        category_name="Service 통합 관심사 A",
    )
    category_two = create_test_category(
        db_session,
        category_name="Service 통합 관심사 B",
    )
    category_three = create_test_category(
        db_session,
        category_name="Service 통합 관심사 C",
    )

    initial_interests = create_user_interests(
        db_session,
        user_id=user.user_id,
        category_ids=[
            category_one.category_id,
            category_two.category_id,
        ],
    )

    db_session.commit()

    kept_interest_before = next(
        interest
        for interest in initial_interests
        if interest.category_id
        == category_one.category_id
    )

    kept_interest_id_before = (
        kept_interest_before.user_interest_id
    )
    kept_created_at_before = (
        kept_interest_before.created_at
    )

    service = build_service(
        db_session,
    )

    result = service.update_interests(
        user_id=user.user_id,
        category_ids=[
            category_one.category_id,
            category_three.category_id,
        ],
    )

    assert result.selected_category_ids == [
        category_one.category_id,
        category_three.category_id,
    ]
    assert result.selected_count == 2

    final_interests = find_interest_rows(
        db_session,
        user_id=user.user_id,
    )

    assert [
        interest.category_id
        for interest in final_interests
    ] == [
        category_one.category_id,
        category_three.category_id,
    ]

    kept_interest_after = next(
        interest
        for interest in final_interests
        if interest.category_id
        == category_one.category_id
    )

    assert (
        kept_interest_after.user_interest_id
        == kept_interest_id_before
    )
    assert (
        kept_interest_after.created_at
        == kept_created_at_before
    )


def test_update_interests_restores_original_state_after_save_failure(
    db_session: Session,
) -> None:
    """delete 이후 save 실패 시 rollback으로 실제 DB 상태를 복원한다."""

    user = create_test_user(
        db_session,
        name="Service 통합 Rollback 사용자",
    )

    category_one = create_test_category(
        db_session,
        category_name="Service Rollback 관심사 A",
    )
    category_two = create_test_category(
        db_session,
        category_name="Service Rollback 관심사 B",
    )
    category_three = create_test_category(
        db_session,
        category_name="Service Rollback 관심사 C",
    )

    initial_interests = create_user_interests(
        db_session,
        user_id=user.user_id,
        category_ids=[
            category_one.category_id,
            category_two.category_id,
        ],
    )

    db_session.commit()

    initial_interest_ids = {
        interest.category_id: interest.user_interest_id
        for interest in initial_interests
    }

    failing_repository = FailingSaveInterestRepository(
        db=db_session,
    )

    service = build_service(
        db_session,
        interest_repository=failing_repository,
    )

    with pytest.raises(
        SQLAlchemyError,
        match="관심사 저장 강제 실패",
    ):
        service.update_interests(
            user_id=user.user_id,
            category_ids=[
                category_one.category_id,
                category_three.category_id,
            ],
        )

    final_interests = find_interest_rows(
        db_session,
        user_id=user.user_id,
    )

    assert [
        interest.category_id
        for interest in final_interests
    ] == [
        category_one.category_id,
        category_two.category_id,
    ]

    assert {
        interest.category_id: interest.user_interest_id
        for interest in final_interests
    } == initial_interest_ids
