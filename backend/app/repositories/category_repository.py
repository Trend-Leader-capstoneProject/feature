from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category


class CategoryRepository:
    """카테고리 데이터 접근을 담당하는 Repository."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def find_all_active(self) -> list[Category]:
        """
        활성 카테고리를 조회한다.

        결과는 sort_order 오름차순, category_id 오름차순으로 반환한다.
        계층 구조 조립은 Service에서 처리한다.
        """

        statement = (
            select(Category)
            .where(Category.is_active.is_(True))
            .order_by(
                Category.sort_order.asc(),
                Category.category_id.asc(),
            )
        )

        return list(self.db.scalars(statement).all())
