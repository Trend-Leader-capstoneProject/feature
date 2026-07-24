from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    DateTime,
    Boolean,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)

from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.db_enums import UserStatus, get_enum_values

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
        String(255),
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
    
    
    def __repr__(self) -> str:
        return (
            "User("
            f"user_id={self.user_id!r}, "
            f"login_id={self.login_id!r}, "
            f"status={self.status!r}"
            ")"
        )
        
        # 민감한 인증 정보는 로그에 출력되지 않도록.