from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.user import User


class UserInterestCategory(Base):
    """사용자와 관심 카테고리의 선택 관계를 저장하는 모델."""

    __tablename__ = "user_interest_categories"
    __table_args__ = (
        # 같은 사용자가 동일한 카테고리를 중복 선택하지 못하게 한다.
        UniqueConstraint(
            "user_id",
            "category_id",
            name="uq_user_interest_categories_user_id_category_id",
        ),
        {
            "comment": "사용자 관심사 카테고리",
        },
    )

    user_interest_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="사용자 관심사 ID 일련번호",
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "users.user_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        comment="사용자 ID",
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        comment="관심 카테고리 선택 시각",
    )

    # 관심사를 선택한 사용자로 접근한다.
    user: Mapped[User] = relationship(
        "User",
        back_populates="interest_category_links",
    )

    # 사용자가 선택한 카테고리로 접근한다.
    category: Mapped[Category] = relationship(
        "Category",
        back_populates="user_interest_links",
    )

    def __repr__(self) -> str:
        return (
            "UserInterestCategory("
            f"user_interest_id={self.user_interest_id!r}, "
            f"user_id={self.user_id!r}, "
            f"category_id={self.category_id!r}"
            ")"
        )
