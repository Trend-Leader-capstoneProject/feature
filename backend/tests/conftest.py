from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_ENV_PATH = BACKEND_DIR / ".env.test"

load_dotenv(
    TEST_ENV_PATH,
    override=False,
)


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """안전한 테스트 전용 DB URL을 반환한다."""

    database_url = os.getenv("TEST_DATABASE_URL")

    if not database_url:
        pytest.skip("TEST_DATABASE_URL이 설정되지 않아 DB 통합 테스트를 건너뜁니다.")

    parsed_url = make_url(database_url)
    database_name = parsed_url.database

    if database_name != "trend_leader_test":
        raise RuntimeError(
            "DB 통합 테스트는 trend_leader_test 데이터베이스에서만 실행할 수 있습니다."
        )

    return database_url


@pytest.fixture(scope="session")
def migrated_test_database(
    test_database_url: str,
) -> str:
    """테스트 DB를 최신 Alembic Revision까지 마이그레이션한다."""

    process_environment = os.environ.copy()
    process_environment["DATABASE_URL"] = test_database_url

    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "upgrade",
            "head",
        ],
        cwd=BACKEND_DIR,
        env=process_environment,
        check=True,
    )

    return test_database_url


@pytest.fixture(scope="session")
def test_engine(
    migrated_test_database: str,
) -> Generator[Engine, None, None]:
    """테스트 세션 동안 사용할 SQLAlchemy Engine을 생성한다."""

    engine = create_engine(
        migrated_test_database,
        pool_pre_ping=True,
    )

    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(
    test_engine: Engine,
) -> Generator[Session, None, None]:
    """
    테스트별 DB Session을 제공한다.

    테스트가 commit을 호출하더라도 외부 Transaction은 유지하며,
    테스트 종료 시 전체 변경을 rollback한다.
    """

    connection = test_engine.connect()
    transaction = connection.begin()

    session = Session(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
