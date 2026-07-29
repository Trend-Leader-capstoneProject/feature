from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.trend import Trend


class TrendCategoryMap(Base):
    """트렌드와 카테고리의 다대다 연결 정보를 저장하는 모델."""

    __tablename__ = "trend_category_map"
    __table_args__ = (
        # 동일 트렌드에 같은 카테고리를 중복 연결하지 못하게 한다.
        UniqueConstraint(
            "trend_id",
            "category_id",
            name="uq_trend_category_map_trend_id_category_id",
        ),
        # 특정 카테고리에 연결된 트렌드를 조회할 때 사용한다.
        Index(
            "ix_trend_category_map_category_id_trend_id",
            "category_id",
            "trend_id",
        ),
        {
            "comment": "트렌드-카테고리 매핑 테이블",
        },
    )

    trend_category_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="트렌드 카테고리 매핑 ID 일련번호",
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        comment="대표 카테고리 여부",
    )

    category_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "categories.category_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        comment="카테고리 ID",
    )

    trend_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "trends.trend_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        comment="트렌드 ID",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        comment="카테고리 연결 시각",
    )

    # 이 매핑에 연결된 트렌드로 접근한다.
    trend: Mapped[Trend] = relationship(
        "Trend",
        back_populates="category_links",
    )

    # 이 매핑에 연결된 카테고리로 접근한다.
    category: Mapped[Category] = relationship(
        "Category",
        back_populates="trend_category_links",
    )

    def __repr__(self) -> str:
        return (
            "TrendCategoryMap("
            f"trend_category_id={self.trend_category_id!r}, "
            f"trend_id={self.trend_id!r}, "
            f"category_id={self.category_id!r}, "
            f"is_primary={self.is_primary!r}"
            ")"
        )
