from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserProfile(Base):
    """사용자의 화면 표시용 프로필 정보를 저장하는 모델."""

    __tablename__ = "user_profiles"
    __table_args__ = (
        # 사용자 한 명당 하나의 프로필만 생성할 수 있다.
        UniqueConstraint(
            "user_id",
            name="uq_user_profiles_user_id",
        ),
        {
            "comment": "사용자 프로필",
        },
    )

    profile_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="프로필 ID 일련번호",
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

    nickname: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="화면 표시용 닉네임",
    )

    profile_image_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="프로필 이미지 경로",
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        onupdate=func.current_timestamp(),
        comment="수정 시각",
    )

    # 이 프로필을 소유한 사용자로 접근한다.
    user: Mapped[User] = relationship(
        "User",
        back_populates="profile",
    )

    def __repr__(self) -> str:
        return (
            "UserProfile("
            f"profile_id={self.profile_id!r}, "
            f"user_id={self.user_id!r}, "
            f"nickname={self.nickname!r}"
            ")"
        )
