from datetime import datetime

from pydantic import BaseModel

from app.models.db_enums import (
    CategoryCode,
    TrendSourcePlatform,
)


class TrendCategoryParent(BaseModel):
    """Trend Category의 상위 대분류 정보."""

    category_id: int
    category_code: CategoryCode | None
    category_name: str


class TrendCategoryItem(BaseModel):
    """Trend에 연결된 세부분류 Category 정보."""

    category_id: int
    category_name: str
    parent: TrendCategoryParent


class TrendLatestSource(BaseModel):
    """Trend 목록에서 노출하는 가장 최근 Source."""

    source_id: int
    platform: TrendSourcePlatform
    source_title: str | None
    source_url: str


class TrendListItem(BaseModel):
    """전체 Trend 목록의 개별 Trend 항목."""

    trend_id: int
    title: str
    summary: str | None
    thumbnail_url: str | None
    last_collected_at: datetime
    categories: list[TrendCategoryItem]
    latest_source: TrendLatestSource | None

class TrendListData(BaseModel):
    """Cursor 기반 Trend 목록 조회 결과."""

    items: list[TrendListItem]
    next_cursor: str | None
    has_next: bool
