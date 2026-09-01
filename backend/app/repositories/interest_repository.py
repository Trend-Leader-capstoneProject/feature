from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models.user_interest_category import UserInterestCategory


class InterestRepository:
    """사용자 관심사 데이터 접근을 담당하는 Repository."""

    def __init__(
        self,
        db: Session
    ) -> None:
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

        return bool(self.db.scalar(
            statement
        )
    )

    def find_by_user_id(
        self,
        user_id: int,
    ) -> list[UserInterestCategory]:
        """사용자의 현재 관심사 목록을 조회한다."""

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
            self.db.scalars(
                statement,
            ).all()
        )

    def find_by_user_id_for_update(
        self,
        user_id: int,
    ) -> list[UserInterestCategory]:
        """사용자의 현재 관심사 Row를 수정용으로 잠그고 조회한다."""

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
            .with_for_update()
        )

        return list(
            self.db.scalars(
                statement,
            ).all()
        )



    def save(
        self,
        user_interests: list[UserInterestCategory],
    ) -> list[UserInterestCategory]:
        """사용자 관심사 여러 건을 현재 Transaction에 추가한다."""

        self.db.add_all(user_interests)
        self.db.flush()

        return user_interests

    def delete(
        self,
        user_interests: list[UserInterestCategory],
    ) -> None:
        """사용자 관심사 여러 건을 현재 Transaction에서 제거한다."""

        for user_interest in user_interests:
            self.db.delete(
                user_interest,
            )

        self.db.flush()
