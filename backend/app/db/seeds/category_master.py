from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.db_enums import CategoryCode


class CategorySeedConflictError(RuntimeError):
    """기존 Category가 Seed 정의와 충돌하거나 식별이 모호할 때 발생한다."""


@dataclass(frozen=True)
class RootCategorySeed:
    """대분류와 그에 속한 세부분류의 초기 Seed 정의."""

    category_code: CategoryCode
    category_name: str
    sort_order: int
    children: tuple[tuple[str, int], ...]


CATEGORY_MASTER: tuple[RootCategorySeed, ...] = (
    RootCategorySeed(
        category_code=CategoryCode.FASHION,
        category_name="패션",
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
    RootCategorySeed(
        category_code=CategoryCode.BEAUTY,
        category_name="뷰티",
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
    RootCategorySeed(
        category_code=CategoryCode.GAME,
        category_name="게임",
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
    RootCategorySeed(
        category_code=CategoryCode.FOOD,
        category_name="음식",
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
    RootCategorySeed(
        category_code=CategoryCode.ENTERTAINMENT,
        category_name="엔터테인먼트",
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
    RootCategorySeed(
        category_code=CategoryCode.IT_DIGITAL,
        category_name="IT/디지털",
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
)


def seed_category_master(db_session: Session) -> None:
    """초기 Master 데이터를 생성한다. 재실행·충돌 검증은 후속 구현한다."""

    try:
        for root_seed in CATEGORY_MASTER:
            root = Category(
                category_code=root_seed.category_code,
                category_name=root_seed.category_name,
                sort_order=root_seed.sort_order,
                is_active=True,
                parent_id=None,
            )

            db_session.add(root)
            db_session.flush()

            for child_name, child_sort_order in root_seed.children:
                child = Category(
                    category_code=None,
                    category_name=child_name,
                    sort_order=child_sort_order,
                    is_active=True,
                    parent_id=root.category_id,
                )

                db_session.add(child)

        db_session.commit()

    except Exception:
        db_session.rollback()
        raise
