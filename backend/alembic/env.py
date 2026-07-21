from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path
from typing import Any

from alembic import context
from sqlalchemy import create_engine, pool

# alembic 명령을 repository root에서 실행해도
# backend/app 패키지를 찾을 수 있도록 경로를 등록한다.
BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402

# 실제 ORM 모델 모듈을 import해야 Base.metadata에 테이블이 등록된다.
import app.models  # noqa: E402, F401


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
target_metadata = Base.metadata

COMMON_CONTEXT_OPTIONS: dict[str, Any] = {
    "target_metadata": target_metadata,
    "compare_type": True,
    "compare_server_default": False,
    "include_schemas": False,
}

def run_migrations_offline() -> None:
    """
    DB에 직접 연결하지 않고 SQL migration 문장을 생성한다.

    실행 예:
        python -m alembic upgrade head --sql
    """
    context.configure(
        url=settings.sync_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **COMMON_CONTEXT_OPTIONS,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    실제 DB에 연결하여 migration을 실행한다.

    API 서버의 connection pool과 migration 실행을 분리하기 위해
    Alembic 전용 Engine은 NullPool로 생성한다.
    """
    connectable = create_engine(
        settings.sync_database_url,
        poolclass=pool.NullPool,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": settings.db_connection_timeout,
            "charset": "utf8mb4",
        },
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            transaction_per_migration=True,
            **COMMON_CONTEXT_OPTIONS,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()