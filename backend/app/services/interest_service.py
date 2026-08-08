from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.models.category import Category
from app.models.user_interest_category import UserInterestCategory
from app.repositories.category_repository import CategoryRepository
from app.repositories.interest_repository import InterestRepository
from app.schemas.interest_schema import InterestCreateData


class InterestService:
    """사용자 관심사 저장 비즈니스 로직을 담당하는 Service."""
    
    def __init__(
        self,
        db: Session,
        category_repository: CategoryRepository,
        interest_repository: InterestRepository,
    ) -> None:
        self.db = db
        self.category_repository = category_repository
        self.interest_repository = interest_repository
        
    def create_interests(
        self,
        user_id: int,
        category_ids: list[int],
    ) -> InterestCreateData:
        """사용자의 최초 관심사 저장"""
        
        if self.interest_repository.exists_by_user_id(
            user_id,
        ):
            raise ConflictException(
                message="이미 관심사가 저장된 사용자입니다.",
            )
            
        categories = self.category_repository.find_list_by_ids(
            category_ids,
        )
        
        self._validate_categories(
            category_ids=category_ids,
            categories=categories,
        )
        
        user_interests = self._build_user_interests(
            user_id=user_id,
            category_ids=category_ids,
        )
        
        try:
            self.interest_repository.save(
                user_interests,
            )
            self.db.commit()
            
        except SQLAlchemyError:
            self.db.rollback()
            raise
        
        
        return InterestCreateData(
            selected_category_ids=category_ids,
            selected_count=len(category_ids),
        )
        
    @staticmethod
    def _validate_categories(
        category_ids: list[int],
        categories: list[Category],
    ) -> None:
        """요청된 모든 카테고리가 최초 관심사 선택 규칙을 만족하는지 검증한다."""

        categories_by_id = {
            category.category_id: category
            for category in categories
        }

        missing_category_ids = [
            category_id
            for category_id in category_ids
            if category_id not in categories_by_id
        ]

        if missing_category_ids:
            raise NotFoundException(
                message="존재하지 않는 카테고리가 포함되어 있습니다.",
                data={
                    "category_ids": missing_category_ids,
                },
            )

        ordered_categories = [
            categories_by_id[category_id]
            for category_id in category_ids
        ]

        inactive_category_ids = [
            category.category_id
            for category in ordered_categories
            if not category.is_active
        ]

        child_category_ids = [
            category.category_id
            for category in ordered_categories
            if category.parent_id is not None
        ]

        if inactive_category_ids or child_category_ids:
            raise BadRequestException(
                message=(
                    "활성 상태의 대분류 카테고리만 "
                    "관심사로 선택할 수 있습니다."
                ),
                data={
                    "inactive_category_ids": inactive_category_ids,
                    "child_category_ids": child_category_ids,
                },
            )

    @staticmethod
    def _build_user_interests(
        user_id: int,
        category_ids: list[int],
    ) -> list[UserInterestCategory]:
        """검증된 카테고리 ID로 사용자 관심사 ORM 객체를 생성한다."""

        return [
            UserInterestCategory(
                user_id=user_id,
                category_id=category_id,
            )
            for category_id in category_ids
        ]