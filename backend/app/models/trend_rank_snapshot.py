from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.db_enums import TrendSourcePlatform, get_enum_values

if TYPE_CHECKING:
    from app.models.trend import Trend


class TrendRankSnapshot(Base):
    """플랫폼별 트렌드 순위를 시계열로 저장하는 모델."""

    __tablename__ = "trend_rank_snapshots"
    __table_args__ = (
        # 동일 트렌드·플랫폼·시각의 중복 스냅샷 생성을 막는다.
        UniqueConstraint(
            "trend_id",
            "platform",
            "snapshot_at",
            name=("uq_trend_rank_snapshots_trend_id_platform_snapshot_at"),
        ),
        # 특정 플랫폼의 특정 시점 순위를 순위순으로 조회할 때 사용한다.
        Index(
            "ix_trend_rank_snapshots_platform_snapshot_at_ranking",
            "platform",
            "snapshot_at",
            "ranking",
        ),
        # 특정 트렌드의 순위 변동 이력을 시간순으로 조회할 때 사용한다.
        Index(
            "ix_trend_rank_snapshots_trend_id_snapshot_at",
            "trend_id",
            "snapshot_at",
        ),
        {
            "comment": "트렌드 순위 스냅샷",
        },
    )

    rank_snapshot_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="순위 기록 ID 일련번호",
    )

    platform: Mapped[TrendSourcePlatform] = mapped_column(
        SqlEnum(
            TrendSourcePlatform,
            name="trend_rank_platform",
            values_callable=get_enum_values,
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            length=30,
        ),
        nullable=False,
        comment="순위 기준 플랫폼",
    )

    ranking: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="수집 시점의 플랫폼 순위",
    )

    rank_delta: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="직전 순위 대비 순위 변동값",
    )

    score: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
        comment="플랫폼에서 제공한 트렌드 점수",
    )

    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        comment="스냅샷 시각",
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

    # 이 순위 스냅샷이 속한 트렌드로 접근한다.
    trend: Mapped[Trend] = relationship(
        "Trend",
        back_populates="rank_snapshots",
    )

    def __repr__(self) -> str:
        return (
            "TrendRankSnapshot("
            f"rank_snapshot_id={self.rank_snapshot_id!r}, "
            f"trend_id={self.trend_id!r}, "
            f"platform={self.platform!r}, "
            f"ranking={self.ranking!r}, "
            f"rank_delta={self.rank_delta!r}"
            ")"
        )
