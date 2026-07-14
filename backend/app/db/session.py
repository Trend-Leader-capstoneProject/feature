"""
SQLAlchemy Engine, SessionFactory, FastAPI DB 의존성 구성.

주요 책임:
- SQLAlchemy Engine 생성
- Connection Pool 설정
- 요청 단위 Session 생성
- 예외 발생 시 rollback
- 요청 종료 시 Session close 보장
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.sync_database_url,

    # Pool에 남아 있던 연결이 유효한지 checkout 시점에 확인한다.
    pool_pre_ping=True,

    # 기본 연결 풀 설정
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,

    # MySQL/MariaDB가 오래된 연결을 종료하는 상황에 대응한다.
    pool_recycle=settings.db_pool_recycle,

    # DB 중단 시 너무 오랫동안 대기하지 않도록 제한한다.
    connect_args={
        "connect_timeout": settings.db_connection_timeout,
        "charset": "utf8mb4",
    },
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    
    # 쿼리 실행 전 자동 flush를 방지한다.
    autoflush=False,
    
    # commit 이후에도 ORM 객체의 속성값을 유지한다.
    expire_on_commit=False,
)

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI 요청 단위 DB Session 의존성.

    요청이 시작되면 Session을 생성하고,
    요청 처리 중 예외가 발생하면 rollback한 뒤 예외를 다시 전달한다.

    요청 성공/실패 여부와 관계없이 finally에서 Session을 닫는다.
    """
    db = SessionLocal()
    
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    
    finally:
        db.close()