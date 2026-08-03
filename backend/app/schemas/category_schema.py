from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.db_enums import CategoryCode


class CategoryItem(BaseModel):
    """
    카테고리 목록의 개별 항목.

    대분류에는 category_code가 존재하고,
    세부분류의 category_code는 null일 수 있다.
    """

    category_id: int
    category_code: CategoryCode | None
    category_name: str
    parent_id: int | None
    sort_order: int
    children: list[CategoryItem] = Field(default_factory=list)


class CategoryListData(BaseModel):
    """카테고리 목록 조회 응답의 실제 데이터"""

    categories: list[CategoryItem]
