from __future__ import annotations
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum as SqlEnum,
    String,
    UniqueConstraint,
    func,
)

from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.db_enums import UserStatus, get_enum_values


if TYPE_CHECKING:
    from app.models.oauth_account import OAuthAccount
    from app.models.user_profile import UserProfile

class User(Base):
    """사용자 계정 정보를 저장하는 모델."""
    
    __tablename__ = "users"
    __table_args__ = (
        # NULL이 아닌 로그인 ID는 중복될 수 없다.
        UniqueConstraint(
            "login_id",
            name="uq_users_login_id",
        ),
        # NULL이 아닌 이메일은 중복될 수 없다.
        UniqueConstraint(
            "email",
            name="uq_users_email",
        ),
        {
            "comment": "사용자",
        },
    )

    
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="사용자 ID 일련번호",
    )
    
    login_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="로그인 ID",
    )
    
    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="비밀번호 해시값",
    )
    
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="사용자 이름",
    )
    
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="이메일 & OAuth 연동",
    )
    
    status: Mapped[UserStatus] = mapped_column(
        SqlEnum(
            UserStatus,
            name="user_status",
            values_callable=get_enum_values,
            native_enum=True,
        ),
        nullable=False,
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE.value,
        comment="계정 상태",
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        comment="사용자 가입 시각",
    )
    
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        onupdate=func.current_timestamp(),
        comment="계정 수정 시각",
    )
    
    withdrawn_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="탈퇴 시각",
    )
    
    withdraw_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="회원 탈퇴 사유",
    )
    
    
    
    # 사용자 한 명은 하나의 프로필만 가진다.
    profile: Mapped["UserProfile | None"] = relationship(
        "UserProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # 하나의 사용자는 여러 OAuth 계정을 연결할 수 있다.
    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(
        "OAuthAccount",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    
    
    def __repr__(self) -> str:
        # 비밀번호 해시와 이메일은 로그에 출력하지 않는다.
        return (
            "User("
            f"user_id={self.user_id!r}, "
            f"login_id={self.login_id!r}, "
            f"status={self.status!r}"
            ")"
        )
