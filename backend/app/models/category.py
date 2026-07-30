from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.search_log import SearchLog
    from app.models.trend_category_map import TrendCategoryMap
    from app.models.user_interest_category import UserInterestCategory


class Category(Base):
    """사용자 관심사와 트렌드를 분류하는 카테고리 모델."""

    __tablename__ = "categories"
    __table_args__ = (
        # 같은 이름의 카테고리가 중복 생성되는 것을 막는다.
        UniqueConstraint(
            "category_name",
            name="uq_categories_category_name",
        ),
        # 상위 카테고리별 활성 하위 카테고리를 노출 순서대로 조회한다.
        Index(
            "ix_categories_parent_id_is_active_sort_order",
            "parent_id",
            "is_active",
            "sort_order",
        ),
        {
            "comment": "카테고리",
        },
    )

    category_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="카테고리 ID 일련번호",
    )

    category_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="카테고리명",
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="화면 노출 순서",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
        comment="사용 여부",
    )

    parent_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "categories.category_id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        comment="상위 카테고리 ID",
    )

    # 세부 카테고리에서 상위 카테고리로 접근한다.
    parent: Mapped[Category | None] = relationship(
        "Category",
        back_populates="children",
        remote_side=lambda: [Category.category_id],
    )

    # 상위 카테고리에서 소속 세부 카테고리 목록으로 접근한다.
    children: Mapped[list[Category]] = relationship(
        "Category",
        back_populates="parent",
        passive_deletes="all",
    )

    # 이 카테고리를 관심사로 선택한 사용자 연결 목록이다.
    user_interest_links: Mapped[list[UserInterestCategory]] = relationship(
        "UserInterestCategory",
        back_populates="category",
        passive_deletes="all",
    )

    # 이 카테고리가 연결된 트렌드 매핑 목록이다.
    trend_category_links: Mapped[list[TrendCategoryMap]] = relationship(
        "TrendCategoryMap",
        back_populates="category",
        passive_deletes="all",
    )

    # 이 카테고리를 필터로 사용한 검색 기록 목록
    search_logs: Mapped[list[SearchLog]] = relationship(
        "SearchLog",
        back_populates="category",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return (
            "Category("
            f"category_id={self.category_id!r}, "
            f"category_name={self.category_name!r}, "
            f"parent_id={self.parent_id!r}"
            ")"
        )
