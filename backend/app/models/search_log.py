from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
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

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.user import User


class SearchLog(Base):
    """사용자별 최근 검색어를 저장하는 모델."""

    __tablename__ = "search_logs"
    __table_args__ = (
        # 같은 사용자의 동일한 정규화 검색어 중복 저장을 막는다.
        UniqueConstraint(
            "user_id",
            "normalized_keyword",
            name="uq_search_logs_user_id_normalized_keyword",
        ),
        # 사용자의 최근 검색어를 검색 시각순으로 조회할 때 사용한다.
        Index(
            "ix_search_logs_user_id_searched_at",
            "user_id",
            "searched_at",
        ),
        {
            "comment": "사용자별 최근 검색어",
        },
    )

    search_log_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="검색 기록 ID 일련번호",
    )

    keyword: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="사용자가 입력한 검색어 원문",
    )

    normalized_keyword: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="중복 비교용 정규화 검색어",
    )

    result_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="검색 결과 건수",
    )

    searched_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        comment="검색 실행 시각",
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "users.user_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        comment="검색을 실행한 사용자 ID",
    )

    category_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "categories.category_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        comment="검색 시 적용한 카테고리 ID",
    )

    # 이 검색 기록을 생성한 사용자로 접근
    user: Mapped[User] = relationship(
        "User",
        back_populates="search_logs",
    )

    # 검색 당시 적용한 카테고리로 접근
    category: Mapped[Category | None] = relationship(
        "Category",
        back_populates="search_logs",
    )

    def __repr__(self) -> str:
        # 사용자가 검색한 원문은 로그에 노출하지 않는다.
        return (
            "SearchLog("
            f"search_log_id={self.search_log_id!r}, "
            f"user_id={self.user_id!r}, "
            f"category_id={self.category_id!r}, "
            f"result_count={self.result_count!r}, "
            f"searched_at={self.searched_at!r}"
            ")"
        )
