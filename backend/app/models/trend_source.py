from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    BigInteger,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.db_enums import TrendSourcePlatform, get_enum_values

if TYPE_CHECKING:
    from app.models.trend import Trend


class TrendSource(Base):
    """트렌드가 수집된 외부 플랫폼의 출처 정보를 저장하는 모델."""

    __tablename__ = "trend_sources"
    __table_args__ = (
        # 같은 트렌드에 동일한 출처가 중복 저장되는 것을 막는다.
        UniqueConstraint(
            "trend_id",
            "source_key",
            name="uq_trend_sources_trend_source_key",
        ),
        {
            "comment": "트렌드 출처 정보 저장",
        },
    )

    source_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="출처 ID 일련번호",
    )

    source_key: Mapped[str] = mapped_column(
        CHAR(64),
        nullable=False,
        comment="중복 비교용 출처 SHA-256 해시값",
    )

    source_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="원문 또는 수집 URL",
    )

    source_title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="수집 자료 제목",
    )

    platform: Mapped[TrendSourcePlatform] = mapped_column(
        SqlEnum(
            TrendSourcePlatform,
            name="trend_source_platform",
            values_callable=get_enum_values,
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            length=30,
        ),
        nullable=False,
        comment="수집 플랫폼",
    )

    collected_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        comment="수집 시각",
    )

    external_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="외부 플랫폼 사용자 또는 콘텐츠 식별값",
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

    # 이 출처가 연결된 트렌드로 접근한다.
    trend: Mapped[Trend] = relationship(
        "Trend",
        back_populates="sources",
    )

    def __repr__(self) -> str:
        return (
            "TrendSource("
            f"source_id={self.source_id!r}, "
            f"trend_id={self.trend_id!r}, "
            f"platform={self.platform!r}, "
            f"source_key={self.source_key!r}"
            ")"
        )
