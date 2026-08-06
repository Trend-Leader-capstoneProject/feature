from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models.user_interest_category import UserInterestCategory


class InterestRepository:
    """사용자 관심사 데이터 접근을 담당하는 Repository."""
    
    def __init__(self, db: Session) -> None:
        self.db = db
        
    def exists_by_user_id(
        self,
        user_id: int,
    ) -> bool:
        """사용자에게 저장된 관심사가 하나 이상 있는지 확인한다."""
        
        statement = select(
            exists().where(
                UserInterestCategory.user_id == user_id,
            ),
        )
        
        return bool(self.db.scalar(statement))
    
    def save(
        self,
        user_interests: list[UserInterestCategory],
    ) -> list[UserInterestCategory]:
        """사용자 관심사 여러 건을 현재 Transaction에 추가한다."""
        
        self.db.add_all(user_interests)
        self.db.flush()
        
        return user_interests