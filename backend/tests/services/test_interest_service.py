from typing import cast
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.models.category import Category
from app.models.db_enums import CategoryCode
from app.models.user_interest_category import UserInterestCategory
from app.repositories.category_repository import CategoryRepository
from app.repositories.interest_repository import InterestRepository
from app.services.interest_service import InterestService


def make_category(
    category_id: int,
    *,
    category_code: CategoryCode | None = CategoryCode.GAME,
    is_active: bool = True,
    parent_id: int | None = None,
) -> Category:
    """InterestService 테스트용 Category를 생성한다."""

    return Category(
        category_id=category_id,
        category_code=category_code,
        category_name=f"테스트 카테고리 {category_id}",
        sort_order=category_id,
        is_active=is_active,
        parent_id=parent_id,
    )


def make_interest(
    *,
    user_id: int,
    category_id: int,
) -> UserInterestCategory:
    """InterestService 테스트용 사용자 관심사를 생성한다."""

    return UserInterestCategory(
        user_id=user_id,
        category_id=category_id,
    )


def make_service() -> tuple[InterestService, Mock, Mock, Mock]:
    """Mock 의존성을 사용하는 InterestService를 생성한다."""

    db_mock = Mock(
        spec=Session,
    )
    category_repository_mock = Mock(
        spec=CategoryRepository,
    )
    interest_repository_mock = Mock(
        spec=InterestRepository,
    )

    interest_repository_mock.exists_by_user_id.return_value = False

    service = InterestService(
        db=cast(
            Session,
            db_mock,
        ),
        category_repository=cast(
            CategoryRepository,
            category_repository_mock,
        ),
        interest_repository=cast(
            InterestRepository,
            interest_repository_mock,
        ),
    )

    return (
        service,
        db_mock,
        category_repository_mock,
        interest_repository_mock,
    )


def test_create_interests_saves_and_commits() -> None:
    """유효한 대분류 관심사를 저장하고 Transaction을 commit한다."""

    (
        service,
        db_mock,
        category_repository_mock,
        interest_repository_mock,
    ) = make_service()

    category_ids = [
        1,
        2,
    ]

    category_repository_mock.find_list_by_ids.return_value = [
        make_category(
            1,
            category_code=CategoryCode.GAME,
        ),
        make_category(
            2,
            category_code=CategoryCode.FOOD,
        ),
    ]

    result = service.create_interests(
        user_id=100,
        category_ids=category_ids,
    )

    assert result.model_dump() == {
        "selected_category_ids": [
            1,
            2,
        ],
        "selected_count": 2,
    }

    interest_repository_mock.exists_by_user_id.assert_called_once_with(
        100,
    )
    category_repository_mock.find_list_by_ids.assert_called_once_with(
        category_ids,
    )
    interest_repository_mock.save.assert_called_once()

    saved_interests = interest_repository_mock.save.call_args.args[0]

    assert [
        (
            interest.user_id,
            interest.category_id,
        )
        for interest in saved_interests
    ] == [
        (
            100,
            1,
        ),
        (
            100,
            2,
        ),
    ]

    db_mock.commit.assert_called_once_with()
    db_mock.rollback.assert_not_called()


def test_create_interests_raises_conflict_when_already_saved() -> None:
    """이미 관심사가 있으면 409 예외를 발생시킨다."""

    (
        service,
        db_mock,
        category_repository_mock,
        interest_repository_mock,
    ) = make_service()

    interest_repository_mock.exists_by_user_id.return_value = True

    with pytest.raises(
        ConflictException,
    ) as exc_info:
        service.create_interests(
            user_id=100,
            category_ids=[
                1,
            ],
        )

    assert exc_info.value.status_code == 409
    assert (
        exc_info.value.message
        == "이미 관심사가 저장된 사용자입니다."
    )

    category_repository_mock.find_list_by_ids.assert_not_called()
    interest_repository_mock.save.assert_not_called()
    db_mock.commit.assert_not_called()
    db_mock.rollback.assert_not_called()


def test_create_interests_raises_not_found_for_missing_category() -> None:
    """요청한 카테고리 중 존재하지 않는 ID가 있으면 404를 발생시킨다."""

    (
        service,
        db_mock,
        category_repository_mock,
        interest_repository_mock,
    ) = make_service()

    category_repository_mock.find_list_by_ids.return_value = [
        make_category(
            1,
        ),
    ]

    with pytest.raises(
        NotFoundException,
    ) as exc_info:
        service.create_interests(
            user_id=100,
            category_ids=[
                1,
                999,
            ],
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.message == (
        "존재하지 않는 카테고리가 포함되어 있습니다."
    )
    assert exc_info.value.data == {
        "category_ids": [
            999,
        ],
    }

    interest_repository_mock.save.assert_not_called()
    db_mock.commit.assert_not_called()
    db_mock.rollback.assert_not_called()


def test_create_interests_raises_bad_request_for_inactive_category() -> None:
    """비활성 카테고리가 포함되면 400을 발생시킨다."""

    (
        service,
        db_mock,
        category_repository_mock,
        interest_repository_mock,
    ) = make_service()

    category_repository_mock.find_list_by_ids.return_value = [
        make_category(
            1,
            is_active=False,
        ),
    ]

    with pytest.raises(
        BadRequestException,
    ) as exc_info:
        service.create_interests(
            user_id=100,
            category_ids=[
                1,
            ],
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.message == (
        "활성 상태의 대분류 카테고리만 "
        "관심사로 선택할 수 있습니다."
    )
    assert exc_info.value.data == {
        "inactive_category_ids": [
            1,
        ],
        "child_category_ids": [],
    }

    interest_repository_mock.save.assert_not_called()
    db_mock.commit.assert_not_called()
    db_mock.rollback.assert_not_called()


def test_create_interests_raises_bad_request_for_child_category() -> None:
    """세부분류 카테고리가 포함되면 400을 발생시킨다."""

    (
        service,
        db_mock,
        category_repository_mock,
        interest_repository_mock,
    ) = make_service()

    category_repository_mock.find_list_by_ids.return_value = [
        make_category(
            2,
            category_code=None,
            parent_id=1,
        ),
    ]

    with pytest.raises(
        BadRequestException,
    ) as exc_info:
        service.create_interests(
            user_id=100,
            category_ids=[
                2,
            ],
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.data == {
        "inactive_category_ids": [],
        "child_category_ids": [
            2,
        ],
    }

    interest_repository_mock.save.assert_not_called()
    db_mock.commit.assert_not_called()
    db_mock.rollback.assert_not_called()


def test_create_interests_rolls_back_when_repository_save_fails() -> None:
    """관심사 저장 중 DB 오류가 발생하면 rollback한다."""

    (
        service,
        db_mock,
        category_repository_mock,
        interest_repository_mock,
    ) = make_service()

    category_repository_mock.find_list_by_ids.return_value = [
        make_category(
            1,
        ),
    ]

    interest_repository_mock.save.side_effect = SQLAlchemyError(
        "관심사 저장 실패",
    )

    with pytest.raises(
        SQLAlchemyError,
    ):
        service.create_interests(
            user_id=100,
            category_ids=[
                1,
            ],
        )

    interest_repository_mock.save.assert_called_once()
    db_mock.commit.assert_not_called()
    db_mock.rollback.assert_called_once_with()


def test_create_interests_rolls_back_when_commit_fails() -> None:
    """commit 중 DB 오류가 발생하면 rollback한다."""

    (
        service,
        db_mock,
        category_repository_mock,
        interest_repository_mock,
    ) = make_service()

    category_repository_mock.find_list_by_ids.return_value = [
        make_category(
            1,
        ),
    ]

    db_mock.commit.side_effect = SQLAlchemyError(
        "commit 실패",
    )

    with pytest.raises(
        SQLAlchemyError,
    ):
        service.create_interests(
            user_id=100,
            category_ids=[
                1,
            ],
        )

    interest_repository_mock.save.assert_called_once()
    db_mock.commit.assert_called_once_with()
    db_mock.rollback.assert_called_once_with()


def test_get_interests_returns_current_user_interests() -> None:
    """사용자의 현재 관심사 목록을 조회한다."""

    (
        service,
        db_mock,
        category_repository_mock,
        interest_repository_mock,
    ) = make_service()

    interest_repository_mock.find_by_user_id.return_value = [
        make_interest(
            user_id=100,
            category_id=1,
        ),
        make_interest(
            user_id=100,
            category_id=3,
        ),
    ]

    result = service.get_interests(
        user_id=100,
    )

    assert result.model_dump() == {
        "selected_category_ids": [
            1,
            3,
        ],
        "selected_count": 2,
    }

    interest_repository_mock.find_by_user_id.assert_called_once_with(
        100,
    )

    category_repository_mock.find_list_by_ids.assert_not_called()
    db_mock.commit.assert_not_called()
    db_mock.rollback.assert_not_called()


def test_get_interests_returns_empty_list_when_not_initialized() -> None:
    """관심사가 없는 사용자는 빈 관심사 목록을 반환한다."""

    (
        service,
        db_mock,
        category_repository_mock,
        interest_repository_mock,
    ) = make_service()

    interest_repository_mock.find_by_user_id.return_value = []

    result = service.get_interests(
        user_id=100,
    )

    assert result.model_dump() == {
        "selected_category_ids": [],
        "selected_count": 0,
    }

    interest_repository_mock.find_by_user_id.assert_called_once_with(
        100,
    )

    category_repository_mock.find_list_by_ids.assert_not_called()
    db_mock.commit.assert_not_called()
    db_mock.rollback.assert_not_called()


def test_update_interests_applies_diff_and_commits() -> None:
    """현재 관심사와 요청 집합의 차이만 반영하고 commit한다."""

    (
        service,
        db_mock,
        category_repository_mock,
        interest_repository_mock,
    ) = make_service()

    current_interest_one = make_interest(
        user_id=100,
        category_id=1,
    )
    current_interest_two = make_interest(
        user_id=100,
        category_id=2,
    )

    category_repository_mock.find_list_by_ids.return_value = [
        make_category(
            1,
            category_code=CategoryCode.GAME,
        ),
        make_category(
            3,
            category_code=CategoryCode.FOOD,
        ),
    ]

    interest_repository_mock.find_by_user_id_for_update.return_value = [
        current_interest_one,
        current_interest_two,
    ]

    result = service.update_interests(
        user_id=100,
        category_ids=[
            1,
            3,
        ],
    )

    assert result.model_dump() == {
        "selected_category_ids": [
            1,
            3,
        ],
        "selected_count": 2,
    }

    category_repository_mock.find_list_by_ids.assert_called_once_with(
        [
            1,
            3,
        ],
    )
    interest_repository_mock.find_by_user_id_for_update.assert_called_once_with(
        100,
    )

    interest_repository_mock.delete.assert_called_once_with(
        [
            current_interest_two,
        ],
    )

    interest_repository_mock.save.assert_called_once()

    saved_interests = (
        interest_repository_mock.save.call_args.args[0]
    )

    assert [
        (
            interest.user_id,
            interest.category_id,
        )
        for interest in saved_interests
    ] == [
        (
            100,
            3,
        ),
    ]

    db_mock.commit.assert_called_once_with()
    db_mock.rollback.assert_not_called()


def test_update_interests_returns_success_without_writes_for_same_set() -> None:
    """동일한 관심사 집합이면 쓰기 없이 200 결과를 생성한다."""

    (
        service,
        db_mock,
        category_repository_mock,
        interest_repository_mock,
    ) = make_service()

    current_interest_one = make_interest(
        user_id=100,
        category_id=1,
    )
    current_interest_two = make_interest(
        user_id=100,
        category_id=2,
    )

    category_repository_mock.find_list_by_ids.return_value = [
        make_category(
            1,
            category_code=CategoryCode.GAME,
        ),
        make_category(
            2,
            category_code=CategoryCode.FOOD,
        ),
    ]

    interest_repository_mock.find_by_user_id_for_update.return_value = [
        current_interest_one,
        current_interest_two,
    ]

    result = service.update_interests(
        user_id=100,
        category_ids=[
            2,
            1,
        ],
    )

    assert result.model_dump() == {
        "selected_category_ids": [
            1,
            2,
        ],
        "selected_count": 2,
    }

    interest_repository_mock.delete.assert_not_called()
    interest_repository_mock.save.assert_not_called()

    db_mock.commit.assert_called_once_with()
    db_mock.rollback.assert_not_called()


def test_update_interests_raises_conflict_when_not_initialized() -> None:
    """수정할 기존 관심사가 없으면 409 상태 충돌을 발생시킨다."""

    (
        service,
        db_mock,
        category_repository_mock,
        interest_repository_mock,
    ) = make_service()

    category_repository_mock.find_list_by_ids.return_value = [
        make_category(
            1,
        ),
    ]

    interest_repository_mock.find_by_user_id_for_update.return_value = []

    with pytest.raises(
        ConflictException,
    ) as exc_info:
        service.update_interests(
            user_id=100,
            category_ids=[
                1,
            ],
        )

    assert exc_info.value.status_code == 409
    assert (
        exc_info.value.message
        == "수정할 기존 관심사가 없습니다."
    )
    assert exc_info.value.data == {
        "reason": "INTERESTS_NOT_INITIALIZED",
    }

    interest_repository_mock.delete.assert_not_called()
    interest_repository_mock.save.assert_not_called()
    db_mock.commit.assert_not_called()


def test_update_interests_raises_not_found_for_missing_category() -> None:
    """수정 요청에 존재하지 않는 카테고리가 있으면 404를 발생시킨다."""

    (
        service,
        db_mock,
        category_repository_mock,
        interest_repository_mock,
    ) = make_service()

    category_repository_mock.find_list_by_ids.return_value = [
        make_category(
            1,
        ),
    ]

    with pytest.raises(
        NotFoundException,
    ) as exc_info:
        service.update_interests(
            user_id=100,
            category_ids=[
                1,
                999,
            ],
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.data == {
        "category_ids": [
            999,
        ],
    }

    interest_repository_mock.find_by_user_id_for_update.assert_not_called()
    interest_repository_mock.delete.assert_not_called()
    interest_repository_mock.save.assert_not_called()
    db_mock.commit.assert_not_called()


def test_update_interests_raises_bad_request_for_inactive_category() -> None:
    """수정 요청에 비활성 카테고리가 있으면 400을 발생시킨다."""

    (
        service,
        db_mock,
        category_repository_mock,
        interest_repository_mock,
    ) = make_service()

    category_repository_mock.find_list_by_ids.return_value = [
        make_category(
            1,
            is_active=False,
        ),
    ]

    with pytest.raises(
        BadRequestException,
    ) as exc_info:
        service.update_interests(
            user_id=100,
            category_ids=[
                1,
            ],
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.data == {
        "inactive_category_ids": [
            1,
        ],
        "child_category_ids": [],
    }

    interest_repository_mock.find_by_user_id_for_update.assert_not_called()
    interest_repository_mock.delete.assert_not_called()
    interest_repository_mock.save.assert_not_called()
    db_mock.commit.assert_not_called()


def test_update_interests_raises_bad_request_for_child_category() -> None:
    """수정 요청에 세부분류 카테고리가 있으면 400을 발생시킨다."""

    (
        service,
        db_mock,
        category_repository_mock,
        interest_repository_mock,
    ) = make_service()

    category_repository_mock.find_list_by_ids.return_value = [
        make_category(
            2,
            category_code=None,
            parent_id=1,
        ),
    ]

    with pytest.raises(
        BadRequestException,
    ) as exc_info:
        service.update_interests(
            user_id=100,
            category_ids=[
                2,
            ],
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.data == {
        "inactive_category_ids": [],
        "child_category_ids": [
            2,
        ],
    }

    interest_repository_mock.find_by_user_id_for_update.assert_not_called()
    interest_repository_mock.delete.assert_not_called()
    interest_repository_mock.save.assert_not_called()
    db_mock.commit.assert_not_called()
