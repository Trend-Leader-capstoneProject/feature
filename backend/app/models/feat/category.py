from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    String,
    text,
)

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# Enum 값은 db_enums.py에서 import 해오기 

from app.models.base.db_enums import CategoryDepth, get_enum_values

class Category(Base):
    """사용자 관심사와 트렌드를 분류하는 카테고리 모델."""
    
    __tablename__ = "categories"
    __table_args__ = {
        "comment": "카테고리",
    }
    
    category_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="카테고리 ID 일련번호",
    )
    
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("categories.category_id"),
        nullable=True,
        index=True,
        comment="상위 카테고리 ID",
    )
    
    category_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="카테고리명",
    )
    
    depth: Mapped[CategoryDepth] = mapped_column(
        SqlEnum(
            CategoryDepth,
            name="category_depth",
            values_callable=get_enum_values,
            native_enum=True,
        ),
        nullable=False,
        default=CategoryDepth.MAIN,
        server_default=CategoryDepth.MAIN.value,
        comment="분류 단계",
    )
    
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="화면 노출 순서",
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        comment="사용 여부",
    )
    
    parent: Mapped[Category | None] = relationship(
        "Category",
        back_populates="children",
        remote_side=lambda: [Category.category_id],
    )
    
    children: Mapped[list[Category]] = relationship(
        "Category",
        back_populates="parent",
    )
    
    def __repr__(self) -> str:
        return (
            "Category("
            f"category_id={self.category_id!r}, "
            f"category_name={self.category_name!r}, "
            f"depth={self.depth!r}"
            ")"
        )