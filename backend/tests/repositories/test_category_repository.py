import pytest
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.db_enums import CategoryCode
from app.repositories.category_repository import CategoryRepository

pytestmark = pytest.mark.integration


def test_find_all_active_returns_only_active_categories_in_order(
    db_session: Session,
) -> None:
    """활성 카테고리만 노출 순서대로 조회하는지 확인한다."""

    categories = [
        Category(
            category_code=None,
            category_name="활성 카테고리 B",
            sort_order=2,
            is_active=True,
            parent_id=None,
        ),
        Category(
            category_code=None,
            category_name="비활성 카테고리",
            sort_order=0,
            is_active=False,
            parent_id=None,
        ),
        Category(
            category_code=None,
            category_name="활성 카테고리 A",
            sort_order=1,
            is_active=True,
            parent_id=None,
        ),
    ]

    db_session.add_all(categories)
    db_session.flush()

    repository = CategoryRepository(
        db=db_session,
    )

    result = repository.find_all_active()

    assert [
        category.category_name
        for category in result
    ] == [
        "활성 카테고리 A",
        "활성 카테고리 B",
    ]


def test_find_all_active_returns_parent_and_children(
    db_session: Session,
) -> None:
    """대분류와 활성 세부분류를 함께 조회하는지 확인한다."""

    root_category = Category(
        category_code=CategoryCode.GAME,
        category_name="통합 테스트 대분류",
        sort_order=1,
        is_active=True,
        parent_id=None,
    )

    db_session.add(root_category)
    db_session.flush()

    child_category = Category(
        category_code=None,
        category_name="통합 테스트 세부분류",
        sort_order=1,
        is_active=True,
        parent_id=root_category.category_id,
    )

    db_session.add(child_category)
    db_session.flush()

    repository = CategoryRepository(
        db=db_session,
    )

    result = repository.find_all_active()

    result_by_name = {
        category.category_name: category
        for category in result
    }

    assert "통합 테스트 대분류" in result_by_name
    assert "통합 테스트 세부분류" in result_by_name

    assert (
        result_by_name["통합 테스트 대분류"].category_code
        == CategoryCode.GAME
    )
    assert (
        result_by_name["통합 테스트 세부분류"].category_code
        is None
    )
    assert (
        result_by_name["통합 테스트 세부분류"].parent_id
        == root_category.category_id
    )
    
def test_find_list_by_ids_returns_matching_categories(
    db_session: Session,
) -> None:
    """요청한 ID에 해당하는 카테고리를 활성 여부와 관계없이 조회한다."""

    active_category = Category(
        category_code=CategoryCode.GAME,
        category_name="ID 조회 활성 카테고리",
        sort_order=1,
        is_active=True,
        parent_id=None,
    )
    inactive_category = Category(
        category_code=CategoryCode.FOOD,
        category_name="ID 조회 비활성 카테고리",
        sort_order=2,
        is_active=False,
        parent_id=None,
    )

    db_session.add_all(
        [
            active_category,
            inactive_category,
        ]
    )
    db_session.flush()

    repository = CategoryRepository(
        db=db_session,
    )

    result = repository.find_list_by_ids(
        [
            active_category.category_id,
            inactive_category.category_id,
        ]
    )

    assert {
        category.category_id
        for category in result
    } == {
        active_category.category_id,
        inactive_category.category_id,
    }