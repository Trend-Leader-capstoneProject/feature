from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.db_enums import RelatedKeywordType, get_enum_values

if TYPE_CHECKING:
    from app.models.trend_ai_analysis import TrendAiAnalysis


class TrendRelatedKeyword(Base):
    """AI 분석을 통해 생성된 트렌드 관련 키워드를 저장하는 모델."""

    __tablename__ = "trend_related_keywords"
    __table_args__ = (
        # 동일 분석에 같은 정규화 키워드가 중복 저장되는 것 방지
        UniqueConstraint(
            "analysis_id",
            "normalized_keyword",
            name=("uq_trend_related_keywords_analysis_id_normalized_keyword"),
        ),
        # 분석별 키워드를 유형과 표시 순서에 따라 조회할 때 사용
        Index(
            "ix_trend_related_keywords_analysis_id_keyword_type_sort_order",
            "analysis_id",
            "keyword_type",
            "sort_order",
        ),
        {
            "comment": "AI 분석 관련 키워드",
        },
    )

    related_keyword_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="관련 키워드 ID 일련번호",
    )

    keyword: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="키워드 이름",
    )

    normalized_keyword: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="중복 비교용 정규화 키워드"
    )

    keyword_type: Mapped[RelatedKeywordType] = mapped_column(
        SqlEnum(
            RelatedKeywordType,
            name="related_keyword_type",
            values_callable=get_enum_values,
            native_enum=True,
        ),
        nullable=False,
        default=RelatedKeywordType.RELATED,
        server_default=RelatedKeywordType.RELATED.value,
        comment="관련 키워드 유형",
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="표시 순서",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        comment="관련 키워드 생성 시각",
    )

    analysis_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "trend_ai_analyses.analysis_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        comment="AI 분석 ID",
    )

    # 이 관련 키워드를 생성한 AI 분석으로 접근
    analysis: Mapped[TrendAiAnalysis] = relationship(
        "TrendAiAnalysis",
        back_populates="related_keywords",
    )

    def __repr__(self) -> str:
        return (
            "TrendRelatedKeyword("
            f"related_keyword_id={self.related_keyword_id!r}, "
            f"analysis_id={self.analysis_id!r}, "
            f"keyword={self.keyword!r}, "
            f"keyword_type={self.keyword_type!r}, "
            f"sort_order={self.sort_order!r}"
            ")"
        )
