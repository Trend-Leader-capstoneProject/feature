"""
SQLAlchemy ORM 모델이 공통으로 상속할 Declarative Base.

향후 app/models 아래에 작성하는 모든 ORM 모델은
이 Base 클래스를 상속한다.
"""

from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """Trend Leader ORM 모델의 공통 Base 클래스."""
    
    pass

