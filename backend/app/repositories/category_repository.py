from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category


class CategoryRepository:
    """카테고리 데이터 접근을 담당하는 Repository."""
    
    def __init__(self, db: Session) -> None:
        self.db = db
        
    def find_all_active(self) -> list[Category]:
        """
        활성 상태인 카테고리 조회
        
        계층 조립 -> 비즈니스 규칙이므로 Service에서 처리
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
    