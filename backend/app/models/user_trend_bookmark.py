from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.trend import Trend
    from app.models.user import User


class UserTrendBookmark(Base):
    """사용자가 저장한 트렌드 북마크 정보를 관리하는 모델."""

    __tablename__ = "user_trend_bookmarks"
    __table_args__ = (
        # 한 사용자가 동일한 트렌드를 중복 저장하지 못하게 한다.
        UniqueConstraint(
            "user_id",
            "trend_id",
            name="uq_user_trend_bookmarks_user_id_trend_id",
        ),
        # 사용자의 북마크 목록을 저장 시각순으로 조회할 때 사용한다.
        Index(
            "ix_user_trend_bookmarks_user_id_created_at",
            "user_id",
            "created_at",
        ),
        {
            "comment": "사용자 저장 트렌드",
        },
    )

    bookmark_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="북마크 ID 일련번호"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        comment="북마크 생성 시각",
    )

    trend_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "trends.trend_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        comment="트렌드 정보 ID",
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

    # 이 북마크를 생성한 사용자로 접근
    user: Mapped[User] = relationship(
        "User",
        back_populates="trend_bookmarks",
    )

    # 이 북마크에 저장된 트렌드로 접근
    trend: Mapped[Trend] = relationship(
        "Trend",
        back_populates="user_bookmarks",
    )

    def __repr__(self) -> str:
        return (
            "UserTrendBookmark("
            f"bookmark_id={self.bookmark_id!r}, "
            f"user_id={self.user_id!r}, "
            f"trend_id={self.trend_id!r}, "
            f"created_at={self.created_at!r}"
            ")"
        )
