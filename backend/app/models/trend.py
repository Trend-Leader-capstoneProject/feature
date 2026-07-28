from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.db_enums import TrendStatus, get_enum_values

if TYPE_CHECKING:
    from app.models.trend_category_map import TrendCategoryMap
    from app.models.trend_rank_snapshot import TrendRankSnapshot
    from app.models.trend_source import TrendSource


class Trend(Base):
    """수집·분석된 트렌드의 기본 정보를 저장하는 모델."""

    __tablename__ = "trends"
    __table_args__ = (
        # 정규화된 제목을 기준으로 같은 트렌드의 중복 생성을 막는다.
        UniqueConstraint(
            "normalized_title",
            name="uq_trends_normalized_title",
        ),
        # 활성 트렌드를 최근 수집 순서로 조회할 때 사용한다.
        Index(
            "ix_trends_status_last_collected_at",
            "status",
            "last_collected_at",
        ),
        {
            "comment": "트렌드 정보",
        },
    )

    trend_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="트렌드 정보 ID",
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="사용자에게 표시할 트렌드 제목",
    )

    normalized_title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="중복 비교용 정규화 트렌드 제목",
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="기본 요약",
    )

    thumbnail_url: Mapped[str | None] = mapped_column(
        Text,
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
        comment="조회 가능 상태",
    )

    first_collected_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        comment="최초 수집 시각",
    )

    last_collected_at: Mapped[datetime] = mapped_column(
        # 같은 트렌드가 다시 수집된 시각
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        comment="마지막 수집 시각",
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        # 제목, 요약, 썸네일, 상태가 변경된 시각
        DateTime,
        nullable=True,
        comment="수정 시각",
    )

    # 트렌드에 연결된 카테고리 매핑 목록
    category_links: Mapped[list[TrendCategoryMap]] = relationship(
        "TrendCategoryMap",
        back_populates="trend",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    
    # 트렌드가 수집된 외부 출처 목록
    sources: Mapped[list[TrendSource]] = relationship(
        "TrendSource",
        back_populates="trend",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    
    # 트렌드의 플랫폼별 순위 변동 이력
    rank_snapshots: Mapped[list[TrendRankSnapshot]] = relationship(
        "TrendRankSnapshot",
        back_populates="trend",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TrendRankSnapshot.snapshot_at",
    )
    
    def __repr__(self) -> str:
        return (
            "Trend("
            f"trend_id={self.trend_id!r}, "
            f"title={self.title!r}, "
            f"status={self.status!r}"
            ")"
        )
