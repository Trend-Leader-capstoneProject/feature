from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.trend import Trend
    from app.models.trend_related_keyword import TrendRelatedKeyword


class TrendAiAnalysis(Base):
    """트렌드에 대한 AI 분석 결과를 버전별로 저장하는 모델."""

    __tablename__ = "trend_ai_analyses"
    __table_args__ = (
        # 동일 트렌드에서 같은 분석 버전이 중복 생성되는 것을 막는다.
        UniqueConstraint(
            "trend_id",
            "analysis_version",
            name="uq_trend_ai_analyses_trend_id_analysis_version",
        ),
        {
            "comment": "트렌드 AI 분석",
        },
    )

    analysis_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="AI 분석 ID 일련번호",
    )

    analysis_version: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="트렌드별 AI 분석 버전"
    )

    one_line_summary: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="AI 한줄 요약"
    )

    reason_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="유행 이유 설명",
    )

    detail_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="상세 설명",
    )

    model_provider: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="AI 모델 제공자",
    )

    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="사용 AI 모델명",
    )

    prompt_version: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="분석 프롬프트 버전",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        comment="AI 분석 생성 시각",
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

    # 이 AI 분석 결과가 속한 트렌드로 접근한다.
    trend: Mapped[Trend] = relationship(
        "Trend",
        back_populates="ai_analyses",
    )

    # 이 AI 분석에서 생성된 관련 키워드 목록
    related_keywords: Mapped[list[TrendRelatedKeyword]] = relationship(
        "TrendRelatedKeyword",
        back_populates="analysis",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return (
            "TrendAiAnalysis("
            f"analysis_id={self.analysis_id!r}, "
            f"trend_id={self.trend_id!r}, "
            f"analysis_version={self.analysis_version!r}, "
            f"model_provider={self.model_provider!r}, "
            f"model_name={self.model_name!r}"
            ")"
        )
