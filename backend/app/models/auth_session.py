from datetime import datetime

from sqlalchemy import CHAR, BigInteger, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuthSession(Base):
    """로그인별 유효성. Refresh 교체와 무관하게 최초 만료일을 유지한다."""

    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index("ix_auth_sessions_user_id", "user_id"),
        Index("ix_auth_sessions_expires_at", "expires_at"),
        {"mysql_engine": "InnoDB"},
    )

    session_id: Mapped[str] = mapped_column(
        CHAR(36, collation="utf8mb4_bin"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_generation: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1
    )
