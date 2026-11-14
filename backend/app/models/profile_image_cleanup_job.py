from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProfileImageCleanupJob(Base):
    """파일 쓰기 전 복구 의도 및 참조 종료 후 삭제 재시도 기록."""

    __tablename__ = "profile_image_cleanup_jobs"
    __table_args__ = (
        UniqueConstraint("file_key", name="uq_profile_image_cleanup_jobs_file_key"),
        {"mysql_engine": "InnoDB"},
    )

    job_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    file_key: Mapped[str] = mapped_column(
        String(100, collation="utf8mb4_bin"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    attempt_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
