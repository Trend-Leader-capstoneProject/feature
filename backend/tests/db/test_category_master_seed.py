from __future__ import annotations

from dataclasses import dataclass

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.seeds.category_master import (
    CategorySeedConflictError,
    seed_category_master,
)
from app.models.category import Category
from app.models.db_enums import CategoryCode

pytestmark = pytest.mark.integration


@dataclass(frozen=True)
class ExpectedRoot:
    """Category Master Seed v1.0의 대분류 계약."""

    name: str
    sort_order: int
    children: tuple[tuple[str, int], ...]


EXPECTED_MASTER: dict[CategoryCode, ExpectedRoot] = {
    CategoryCode.FASHION: ExpectedRoot(
        name="패션",
        sort_order=1,
        children=(
            ("의류", 1),
            ("신발", 2),
            ("가방", 3),
            ("주얼리·액세서리", 4),
            ("패션 스타일", 5),
            ("기타", 99),
        ),
    ),
    CategoryCode.BEAUTY: ExpectedRoot(
        name="뷰티",
        sort_order=2,
        children=(
            ("스킨케어", 1),
            ("메이크업", 2),
            ("헤어", 3),
            ("향수", 4),
            ("네일", 5),
            ("기타", 99),
        ),
    ),
    CategoryCode.GAME: ExpectedRoot(
        name="게임",
        sort_order=3,
        children=(
            ("모바일 게임", 1),
            ("PC 게임", 2),
            ("콘솔 게임", 3),
            ("e스포츠", 4),
            ("게임 플랫폼·서비스", 5),
            ("기타", 99),
        ),
    ),
    CategoryCode.FOOD: ExpectedRoot(
        name="음식",
        sort_order=4,
        children=(
            ("한식", 1),
            ("중식", 2),
            ("일식", 3),
            ("양식", 4),
            ("카페·디저트", 5),
            ("식품·음료", 6),
            ("기타", 99),
        ),
    ),
    CategoryCode.ENTERTAINMENT: ExpectedRoot(
        name="엔터테인먼트",
        sort_order=5,
        children=(
            ("음악", 1),
            ("영화", 2),
            ("드라마", 3),
            ("예능", 4),
            ("웹툰·애니메이션", 5),
            ("연예인·스타", 6),
            ("기타", 99),
        ),
    ),
    CategoryCode.IT_DIGITAL: ExpectedRoot(
        name="IT/디지털",
        sort_order=6,
        children=(
            ("인공지능", 1),
            ("모바일·스마트폰", 2),
            ("PC·하드웨어", 3),
            ("소프트웨어·앱", 4),
            ("플랫폼·서비스", 5),
            ("기타", 99),
        ),
    ),
}


def find_all_categories(db_session: Session) -> list[Category]:
    """Category Row를 ID 순서로 조회한다."""

    statement = select(Category).order_by(Category.category_id)

    return list(db_session.scalars(statement).all())


def add_category(
    db_session: Session,
    *,
    category_code: CategoryCode | None,
    category_name: str,
    sort_order: int,
    is_active: bool,
    parent_id: int | None = None,
) -> Category:
    """Seed 충돌 시나리오에 필요한 기존 Category를 생성한다."""

    category = Category(
        category_code=category_code,
        category_name=category_name,
        sort_order=sort_order,
        is_active=is_active,
        parent_id=parent_id,
    )

    db_session.add(category)
    db_session.flush()

    return category


def assert_master_contract(categories: list[Category]) -> None:
    """조회된 Category가 확정된 6 Root + 38 Child 계약과 일치하는지 확인한다."""

    roots = [category for category in categories if category.parent_id is None]
    children = [category for category in categories if category.parent_id is not None]

    assert len(categories) == 44
    assert len(roots) == 6
    assert len(children) == 38

    roots_by_code = {category.category_code: category for category in roots}

    assert set(roots_by_code) == set(EXPECTED_MASTER)

    other_category_ids: set[int] = set()

    for category_code, expected_root in EXPECTED_MASTER.items():
        root = roots_by_code[category_code]

        assert root.category_name == expected_root.name
        assert root.sort_order == expected_root.sort_order
        assert root.is_active is True

        root_children = sorted(
            (
                category
                for category in children
                if category.parent_id == root.category_id
            ),
            key=lambda category: (category.sort_order, category.category_id),
        )

        assert [
            (category.category_name, category.sort_order)
            for category in root_children
        ] == list(expected_root.children)
        assert all(category.category_code is None for category in root_children)
        assert all(category.is_active is True for category in root_children)

        other = root_children[-1]

        assert other.category_name == "기타"
        assert other.sort_order == 99
        other_category_ids.add(other.category_id)

    assert len(other_category_ids) == 6


def test_seed_creates_exact_category_master_v1_0(
    db_session: Session,
) -> None:
    """첫 실행에서 확정된 6개 대분류와 38개 세부분류를 생성한다."""

    seed_category_master(db_session)

    assert_master_contract(find_all_categories(db_session))


def test_seed_is_idempotent(
    db_session: Session,
) -> None:
    """두 번째 실행에서 Row를 중복 생성하거나 기존 ID를 바꾸지 않는다."""

    seed_category_master(db_session)
    first_category_ids = [
        category.category_id
        for category in find_all_categories(db_session)
    ]

    seed_category_master(db_session)
    second_categories = find_all_categories(db_session)

    assert [
        category.category_id
        for category in second_categories
    ] == first_category_ids
    assert_master_contract(second_categories)


def test_seed_does_not_delete_category_outside_definition(
    db_session: Session,
) -> None:
    """재실행 시 정의 외 Child와 기존 Master 데이터를 그대로 보존한다."""

    seed_category_master(db_session)

    initial_categories = find_all_categories(db_session)
    assert_master_contract(initial_categories)

    game = next(
        category
        for category in initial_categories
        if category.category_code == CategoryCode.GAME
    )

    add_category(
        db_session,
        category_code=None,
        category_name="Seed 정의 외 테스트 분류",
        sort_order=50,
        is_active=False,
        parent_id=game.category_id,
    )

    before = [
        (
            category.category_id,
            category.category_code,
            category.category_name,
            category.parent_id,
            category.sort_order,
            category.is_active,
        )
        for category in find_all_categories(db_session)
    ]

    assert len(before) == 45
    db_session.commit()

    seed_category_master(db_session)

    db_session.expire_all()

    after = [
        (
            category.category_id,
            category.category_code,
            category.category_name,
            category.parent_id,
            category.sort_order,
            category.is_active,
        )
        for category in find_all_categories(db_session)
    ]

    assert len(after) == 45
    assert after == before


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        pytest.param(
            "category_name",
            "과거 음식 이름",
            id="root-name-mismatch",
        ),
        pytest.param(
            "sort_order",
            400,
            id="root-sort-order-mismatch",
        ),
        pytest.param(
            "is_active",
            False,
            id="root-inactive",
        ),
    ],
)
def test_seed_rejects_mismatched_existing_root_and_rolls_back(
    db_session: Session,
    field_name: str,
    invalid_value: str | int | bool,
) -> None:
    """대분류 속성이 다르면 실패하고 기존 데이터와 ID를 보존한다."""

    food = add_category(
        db_session,
        category_code=CategoryCode.FOOD,
        category_name="음식",
        sort_order=4,
        is_active=True,
    )

    setattr(food, field_name, invalid_value)
    db_session.flush()

    before = (
        food.category_id,
        food.category_code,
        food.category_name,
        food.parent_id,
        food.sort_order,
        food.is_active,
    )
    db_session.commit()

    with pytest.raises(CategorySeedConflictError) as exc_info:
        seed_category_master(db_session)

    assert "FOOD" in str(exc_info.value)
    assert field_name in str(exc_info.value)

    db_session.expire_all()
    categories = find_all_categories(db_session)

    assert len(categories) == 1

    remaining = categories[0]

    assert (
        remaining.category_id,
        remaining.category_code,
        remaining.category_name,
        remaining.parent_id,
        remaining.sort_order,
        remaining.is_active,
    ) == before


def test_seed_rejects_root_code_with_parent_and_preserves_data(
    db_session: Session,
) -> None:
    """대분류 코드가 하위 Row에 있으면 실패하고 기존 상태를 보존한다."""

    fashion = add_category(
        db_session,
        category_code=CategoryCode.FASHION,
        category_name="패션",
        sort_order=1,
        is_active=True,
    )

    add_category(
        db_session,
        category_code=CategoryCode.FOOD,
        category_name="음식",
        sort_order=4,
        is_active=True,
        parent_id=fashion.category_id,
    )

    before = [
        (
            category.category_id,
            category.category_code,
            category.category_name,
            category.parent_id,
            category.sort_order,
            category.is_active,
        )
        for category in find_all_categories(db_session)
    ]
    db_session.commit()

    with pytest.raises(CategorySeedConflictError) as exc_info:
        seed_category_master(db_session)

    assert "FOOD" in str(exc_info.value)
    assert "parent_id" in str(exc_info.value)

    db_session.expire_all()

    after = [
        (
            category.category_id,
            category.category_code,
            category.category_name,
            category.parent_id,
            category.sort_order,
            category.is_active,
        )
        for category in find_all_categories(db_session)
    ]

    assert len(after) == 2
    assert after == before


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        pytest.param(
            "sort_order",
            100,
            id="child-sort-order-mismatch",
        ),
        pytest.param(
            "is_active",
            False,
            id="child-inactive",
        ),
    ],
)
def test_seed_rejects_mismatched_existing_child_and_rolls_back(
    db_session: Session,
    field_name: str,
    invalid_value: int | bool,
) -> None:
    """세부분류 속성이 다르면 실패하고 부모와 자식의 상태를 보존한다."""

    game = add_category(
        db_session,
        category_code=CategoryCode.GAME,
        category_name="게임",
        sort_order=3,
        is_active=True,
    )
    mobile_game = add_category(
        db_session,
        category_code=None,
        category_name="모바일 게임",
        sort_order=1,
        is_active=True,
        parent_id=game.category_id,
    )

    setattr(mobile_game, field_name, invalid_value)
    db_session.flush()

    before = [
        (
            category.category_id,
            category.category_code,
            category.category_name,
            category.parent_id,
            category.sort_order,
            category.is_active,
        )
        for category in find_all_categories(db_session)
    ]
    db_session.commit()

    with pytest.raises(CategorySeedConflictError) as exc_info:
        seed_category_master(db_session)

    assert "GAME" in str(exc_info.value)
    assert "모바일 게임" in str(exc_info.value)
    assert field_name in str(exc_info.value)

    db_session.expire_all()

    after = [
        (
            category.category_id,
            category.category_code,
            category.category_name,
            category.parent_id,
            category.sort_order,
            category.is_active,
        )
        for category in find_all_categories(db_session)
    ]

    assert len(after) == 2
    assert after == before

def test_seed_rejects_ambiguous_children_and_rolls_back(
    db_session: Session,
) -> None:
    """동일 부모의 중복 세부분류가 있으면 임의 선택이나 INSERT를 하지 않는다."""

    game = add_category(
        db_session,
        category_code=CategoryCode.GAME,
        category_name="게임",
        sort_order=3,
        is_active=True,
    )

    for _ in range(2):
        add_category(
            db_session,
            category_code=None,
            category_name="기타",
            sort_order=99,
            is_active=True,
            parent_id=game.category_id,
        )

    existing_category_ids = [
        category.category_id
        for category in find_all_categories(db_session)
    ]
    db_session.commit()

    with pytest.raises(CategorySeedConflictError) as exc_info:
        seed_category_master(db_session)

    assert "GAME" in str(exc_info.value)
    assert "기타" in str(exc_info.value)
    assert "중복" in str(exc_info.value)
    assert [
        category.category_id
        for category in find_all_categories(db_session)
    ] == existing_category_ids
