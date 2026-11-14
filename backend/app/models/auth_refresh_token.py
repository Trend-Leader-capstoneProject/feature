from datetime import datetime

from sqlalchemy import CHAR, BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuthRefreshToken(Base):
    """원문을 저장하지 않는 교체 이력. 사용된 해시도 세션 만료까지 보존한다."""

    __tablename__ = "auth_refresh_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_auth_refresh_tokens_token_hash"),
        UniqueConstraint(
            "session_id", "generation", name="uq_auth_refresh_tokens_generation"
        ),
        {"mysql_engine": "InnoDB"},
    )

    token_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    session_id: Mapped[str] = mapped_column(
        CHAR(36, collation="utf8mb4_bin"),
        ForeignKey("auth_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        CHAR(64, collation="utf8mb4_bin"), nullable=False
    )
    generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
