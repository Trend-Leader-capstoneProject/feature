from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.trend import Trend


class TrendRelatedArticle(Base):
    """관측 근거와 별개인 트렌드 참고 기사 링크."""

    __tablename__ = "trend_related_articles"
    __table_args__ = (
        UniqueConstraint(
            "trend_id", "url_key",
            name="uq_trend_related_articles_trend_url_key",
        ),
        UniqueConstraint(
            "trend_id", "selection_order",
            name="uq_trend_related_articles_trend_selection_order",
        ),
        CheckConstraint(
            "selection_order IN (1, 2)",
            name="ck_trend_related_articles_selection_order",
        ),
        CheckConstraint(
            "published_at <= collected_at",
            name="ck_trend_related_articles_published_at",
        ),
        {"comment": "트렌드 참고 기사 링크", "mysql_engine": "InnoDB"},
    )

    article_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True,
        comment="관련 기사 ID",
    )
    trend_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("trends.trend_id", ondelete="CASCADE"),
        nullable=False, comment="부모 트렌드 ID",
    )
    article_url: Mapped[str] = mapped_column(
        Text, nullable=False, comment="승인된 직접 HTTPS 기사 URL",
    )
    url_key: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, comment="정규 기사 URL SHA-256",
    )
    publisher: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="발행 매체",
    )
    title: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="이용 근거가 있는 경우만 저장하는 제목",
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="기사 발행 시각(UTC)",
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="기사 수집 시각(UTC)",
    )
    selection_order: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="기사 표시 순서(1 또는 2)",
    )

    trend: Mapped[Trend] = relationship(
        "Trend", back_populates="related_articles",
    )
