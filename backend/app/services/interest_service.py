from sqlalchemy.exc import DBAPIError, SQLAlchemyError
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
from app.schemas.interest_schema import (
    InterestCreateData,
    InterestReadData,
    InterestUpdateData,
)


class InterestService:
    """사용자 관심사 비즈니스 로직을 담당하는 Service."""

    MAX_UPDATE_ATTEMPTS = 3
    ER_CHECKREAD_CODE = 1020

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
        """사용자의 최초 관심사를 저장한다."""

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

    def get_interests(
        self,
        user_id: int,
    ) -> InterestReadData:
        """사용자의 현재 관심사를 조회한다."""

        user_interests = self.interest_repository.find_by_user_id(
            user_id,
        )

        category_ids = [
            interest.category_id
            for interest in user_interests
        ]

        return InterestReadData(
            selected_category_ids=category_ids,
            selected_count=len(category_ids),
        )

    def update_interests(
        self,
        user_id: int,
        category_ids: list[int],
    ) -> InterestUpdateData:
        """사용자의 기존 관심사 전체 집합을 수정한다."""

        for attempt in range(
            self.MAX_UPDATE_ATTEMPTS,
        ):
            try:
                return self._update_interests_once(
                    user_id=user_id,
                    category_ids=category_ids,
                )

            except DBAPIError as exc:
                self.db.rollback()

                if (
                    not self._is_er_checkread(
                        exc,
                    )
                    or attempt
                    == self.MAX_UPDATE_ATTEMPTS - 1
                ):
                    raise

            except SQLAlchemyError:
                self.db.rollback()
                raise

        raise RuntimeError(
            "관심사 수정 Retry 흐름이 예상하지 못한 상태로 종료되었습니다.",
        )

    def _update_interests_once(
        self,
        *,
        user_id: int,
        category_ids: list[int],
    ) -> InterestUpdateData:
        """하나의 Transaction에서 관심사 전체 교체를 시도한다."""

        categories = self.category_repository.find_list_by_ids(
            category_ids,
        )

        self._validate_categories(
            category_ids=category_ids,
            categories=categories,
        )

        current_interests = (
            self.interest_repository.find_by_user_id_for_update(
                user_id,
            )
        )

        if not current_interests:
            raise ConflictException(
                message="수정할 기존 관심사가 없습니다.",
                data={
                    "reason": "INTERESTS_NOT_INITIALIZED",
                },
            )

        current_by_category_id = {
            interest.category_id: interest
            for interest in current_interests
        }

        current_category_ids = set(
            current_by_category_id,
        )
        requested_category_ids = set(
            category_ids,
        )

        if current_category_ids == requested_category_ids:
            self.db.commit()

            selected_category_ids = sorted(
                requested_category_ids,
            )

            return InterestUpdateData(
                selected_category_ids=selected_category_ids,
                selected_count=len(selected_category_ids),
            )

        remove_category_ids = (
            current_category_ids
            - requested_category_ids
        )
        add_category_ids = (
            requested_category_ids
            - current_category_ids
        )

        remove_interests = [
            current_by_category_id[category_id]
            for category_id in remove_category_ids
        ]

        add_interests = self._build_user_interests(
            user_id=user_id,
            category_ids=list(
                add_category_ids,
            ),
        )

        if remove_interests:
            self.interest_repository.delete(
                remove_interests,
            )

        if add_interests:
            self.interest_repository.save(
                add_interests,
            )

        self.db.commit()

        selected_category_ids = sorted(
            requested_category_ids,
        )

        return InterestUpdateData(
            selected_category_ids=selected_category_ids,
            selected_count=len(selected_category_ids),
        )

    @classmethod
    def _is_er_checkread(
        cls,
        exc: DBAPIError,
    ) -> bool:
        """MariaDB ER_CHECKREAD(1020) 충돌인지 확인한다."""

        original_args = getattr(
            exc.orig,
            "args",
            (),
        )

        return (
            bool(original_args)
            and original_args[0]
            == cls.ER_CHECKREAD_CODE
        )

    @staticmethod
    def _validate_categories(
        category_ids: list[int],
        categories: list[Category],
    ) -> None:
        """요청된 모든 카테고리가 관심사 선택 규칙을 만족하는지 검증한다."""

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
