from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    """사용자 데이터 접근을 담당하는 Repository."""

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def find_by_id(
        self,
        user_id: int,
    ) -> User | None:
        """사용자 ID에 해당하는 사용자를 조회한다."""

        return self.db.get(
            User,
            user_id,
        )