from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum as SqlEnum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.db_enums import TrendStatus, get_enum_values


class Trend(Base):
    """수집·분석된 트렌드의 기본 정보를 저장하는 모델."""

    __tablename__ = "trends"
    __table_args__ = {
        "comment": "트렌드 기본 정보",
    }

    trend_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="트렌드 ID 일련번호",
    )

    trend_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="트렌드명",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="트렌드 간단 설명",
    )

    thumbnail_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="대표 이미지 URL",
    )

    status: Mapped[TrendStatus] = mapped_column(
        SqlEnum(
            TrendStatus,
            name="trend_status",
            values_callable=get_enum_values,
            native_enum=True,
        ),
        nullable=False,
        default=TrendStatus.ACTIVE,
        server_default=TrendStatus.ACTIVE.value,
        comment="노출 상태",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="생성 일시",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="수정 일시",
    )

    def __repr__(self) -> str:
        return (
            "Trend("
            f"trend_id={self.trend_id!r}, "
            f"trend_name={self.trend_name!r}, "
            f"status={self.status!r}"
            ")"
        )
