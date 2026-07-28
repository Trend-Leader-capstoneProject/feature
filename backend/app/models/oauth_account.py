from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.db_enums import OAuthProvider, get_enum_values

if TYPE_CHECKING:
    from app.models.user import User


class OAuthAccount(Base):
    """사용자와 외부 OAuth 계정의 연결 정보를 저장하는 모델."""

    __tablename__ = "oauth_accounts"
    __table_args__ = (
        # 같은 OAuth 계정이 여러 사용자에게 중복 연결되는 것을 막는다.
        UniqueConstraint(
            "provider",
            "provider_user_id",
            name="uq_oauth_accounts_provider_provider_user_id",
        ),
        {
            "comment": "OAuth 계정",
        },
    )

    oauth_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="OAuth 계정 ID 일련번호",
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

    provider: Mapped[OAuthProvider] = mapped_column(
        SqlEnum(
            OAuthProvider,
            name="oauth_provider",
            values_callable=get_enum_values,
            native_enum=True,
        ),
        nullable=False,
        default=OAuthProvider.GOOGLE,
        server_default=OAuthProvider.GOOGLE.value,
        comment="정보 제공자",
    )

    provider_user_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="외부 서비스 사용자 식별값",
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="OAuth 이메일",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        comment="OAuth 계정 연동 시각",
    )

    # OAuth 계정이 연결된 사용자로 접근한다.
    user: Mapped[User] = relationship(
        "User",
        back_populates="oauth_accounts",
    )

    def __repr__(self) -> str:
        # OAuth 이메일은 개인정보이므로 출력하지 않는다.

        return (
            "OAuthAccount("
            f"oauth_id={self.oauth_id!r}, "
            f"user_id={self.user_id!r}, "
            f"provider={self.provider!r}"
            ")"
        )
