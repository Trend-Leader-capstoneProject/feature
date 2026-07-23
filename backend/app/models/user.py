from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    DateTime,
    Boolean,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    String,
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
    __table_args__ = {
        "comment": "유저",
    }
    
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="사용자 ID 일련번호",
    )
    
    login_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        comment="로그인 아이디",
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
        comment="계정 생성일시",
    )
    
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        onupdate=func.current_timestamp(),
        comment="계정 수정일시",
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