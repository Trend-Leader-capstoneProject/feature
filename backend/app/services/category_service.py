import logging

from app.models.category import Category
from app.repositories.category_repository import CategoryRepository
from app.schemas.category_schema import CategoryItem, CategoryListData

logger = logging.getLogger(__name__)


class CategoryService:
    """카테고리 목록 조회 비즈니스 로직을 담당하는 Service."""

    def __init__(
        self,
        category_repository: CategoryRepository,
    ) -> None:
        self.category_repository = category_repository

    def list_categories(self) -> CategoryListData:
        """활성 카테고리를 대분류와 세부분류 계층으로 구성한다."""

        categories = self.category_repository.find_all_active()

        root_categories = self._find_root_categories(categories)
        children_by_parent_id = self._group_children_by_parent_id(
            categories,
        )

        root_category_ids = {category.category_id for category in root_categories}

        orphan_parent_ids = set(children_by_parent_id) - root_category_ids

        for parent_id in sorted(orphan_parent_ids):
            logger.warning(
                "활성 세부분류의 유효한 상위 대분류를 찾을 수 없습니다: "
                "parent_id=%s, child_count=%s",
                parent_id,
                len(children_by_parent_id[parent_id]),
            )

        category_items = [
            self._build_category_item(
                category=root_category,
                children=children_by_parent_id.get(
                    root_category.category_id,
                    [],
                ),
            )
            for root_category in root_categories
        ]

        return CategoryListData(
            categories=category_items,
        )

    @staticmethod
    def _find_root_categories(
        categories: list[Category],
    ) -> list[Category]:
        """parent_id가 없는 대분류 카테고리만 반환한다."""

        return [category for category in categories if category.parent_id is None]

    @staticmethod
    def _group_children_by_parent_id(
        categories: list[Category],
    ) -> dict[int, list[Category]]:
        """세부분류를 상위 카테고리 ID 기준으로 묶는다."""

        children_by_parent_id: dict[int, list[Category]] = {}

        for category in categories:
            if category.parent_id is None:
                continue

            children_by_parent_id.setdefault(
                category.parent_id,
                [],
            ).append(category)

        return children_by_parent_id

    @staticmethod
    def _build_category_item(
        category: Category,
        children: list[Category],
    ) -> CategoryItem:
        """대분류와 소속 세부분류를 응답 Schema로 변환한다."""

        child_items = [
            CategoryItem(
                category_id=child.category_id,
                category_name=child.category_name,
                parent_id=child.parent_id,
                sort_order=child.sort_order,
                children=[],
            )
            for child in children
        ]

        return CategoryItem(
            category_id=category.category_id,
            category_name=category.category_name,
            parent_id=category.parent_id,
            sort_order=category.sort_order,
            children=child_items,
        )
