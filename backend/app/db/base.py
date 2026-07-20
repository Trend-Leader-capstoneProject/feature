"""
SQLAlchemy ORM 모델이 공통으로 상속할 Declarative Base.

모든 ORM 모델은 이 Base를 상속해야 하며,
Alembic은 Base.metadata를 기준으로 DB 스키마 변경을 감지한다.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
class Base(DeclarativeBase):
    """Trend Leader ORM 모델의 공통 Base 클래스."""
    
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

