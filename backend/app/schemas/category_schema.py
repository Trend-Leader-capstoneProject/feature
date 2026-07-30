from __future__ import annotations

from pydantic import BaseModel, Field


class CategoryItem(BaseModel):
    """카테고리 목록의 개별 항목"""
    
    category_id: int
    category_name: str
    parent_id: int | None
    sort_order: int
    children: list[CategoryItem] = Field(default_factory=list)
    
class CategoryListData(BaseModel):
    """카테고리 목록 조회 응답의 실제 데이터"""
    
    categories: list[CategoryItem]
    