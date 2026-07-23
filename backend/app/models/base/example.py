from __future__ import annotations

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

"""
이 방식대로 작성할 것... 참고 클래스 파일
"""

class Example(Base):
    """모델 설명."""

    __tablename__ = "examples"
    __table_args__ = {
        "comment": "테이블 설명",
    }

    example_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="기본 키",
    )

    example_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="이름",
    )

    def __repr__(self) -> str:
        return (
            "Example("
            f"example_id={self.example_id!r}, "
            f"example_name={self.example_name!r}"
            ")"
        )