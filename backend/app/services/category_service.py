import logging

from app.repositories.category_repository import CategoryRepository
from app.schemas.category_schema import CategoryItem, CategoryListData

logger = logging.getLogger(__name__)

class CategoryService:
    """카테고리 목록 조회 및 계층 구조 조립 담당"""
    
    def __init__(
        self,
        category_repository: CategoryRepository,
    ) -> None:
        self.category_repository = category_repository
        
    def list_categories(self) -> CategoryListData:
        """
        활성 카테고리를 대분류와 세부분류의 2단계 구조로 반환한다.

        parent_id가 없는 카테고리는 대분류로 판단한다.
        대분류를 부모로 가진 카테고리만 세부분류로 포함한다.
        """
        
        categories = self.category_repository.find_all_active()
        
        category_items = {
            category.category_id: CategoryItem(
                category_id=category.category_id,
                category_name=category.category_name,
                parent_id=category.parent_id,
                sort_order=category.sort_order,
            )
            for category in categories
        }
        
        root_category_ids = {
            category.category_id
            for category in categories
            if category.parent_id is None
        }
        
        root_categories: list[CategoryItem] = []
        
        for category in categories:
            category_item = category_items[category.category_id]
            
            if category.parent_id is None:
                root_categories.append(category_item)
                continue
            
            if category.category_id not in root_category_ids:
                logger.warning(
                    "카테고리는 상위 활성화가 되지 않기에 제외되었습니다."
                    "root category: category_id=%s, parent_id=%s",
                    category.category_id,
                    category.parent_id,
                )
                continue
            
            parent_item = category_items[category.parent_id]
            parent_item.children.append(category_item)
            
        root_categories.sort(
            key=lambda item: (
                item.sort_order,
                item.category_id,
            ),
        )
        
        for root_category in root_categories:
            root_category.children.sort(
                key=lambda item: (
                    item.sort_order,
                    item.category_id,
                ),
            )

        return CategoryListData(
            categories=root_categories,
        )