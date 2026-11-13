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


@pytest.fixture
def demo_seed_approval() -> dict[str, object]:
    """관리자가 별도 승인한 테스트 기대값만 사용한다(URL에서 추출 금지)."""
    keys = ("HOST", "PORT", "DATABASE", "CURRENT_USER")
    values = {key: os.getenv(f"DEMO_SEED_ALLOWED_{key}") for key in keys}
    if any(not value or not value.strip() for value in values.values()):
        pytest.fail("Demo Seed 통합 테스트에 별도 승인 설정 4개가 필요합니다.")
    try:
        port = int(values["PORT"])
    except (TypeError, ValueError):
        pytest.fail("Demo Seed 승인 Port 설정이 올바르지 않습니다.")
    if not 1 <= port <= 65535:
        pytest.fail("Demo Seed 승인 Port 설정이 올바르지 않습니다.")
    return {
        "allowed_host": values["HOST"],
        "allowed_port": port,
        "allowed_database": values["DATABASE"],
        "allowed_current_user": values["CURRENT_USER"],
    }


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """안전한 테스트 전용 DB URL을 반환한다."""

    database_url = os.getenv("TEST_DATABASE_URL")

    if not database_url or database_url == "input_here":
        pytest.skip(
            "TEST_DATABASE_URL이 설정되지 않아 "
            "DB 통합 테스트를 건너뜁니다."
        )

    parsed_url = make_url(database_url)
    database_name = parsed_url.database

    if database_name != "trend_leader_test":
        raise RuntimeError(
            "DB 통합 테스트는 trend_leader_test "
            "데이터베이스에서만 실행할 수 있습니다."
        )

    return database_url


@pytest.fixture(scope="session")
def migrated_test_database(
    test_database_url: str,
    tmp_path_factory: pytest.TempPathFactory,
) -> str:
    """전용 Migration 설정으로 테스트 DB만 Alembic 적용."""
    parsed_url = make_url(test_database_url)
    if (
        parsed_url.database != "trend_leader_test"
        or not parsed_url.host
        or not parsed_url.username
        or parsed_url.password is None
    ):
        raise RuntimeError("Migration test database credentials are incomplete")

    secret_dir = tmp_path_factory.mktemp("migration_test_secret")
    secret_file = secret_dir / "db_password"
    secret_file.write_text(parsed_url.password, encoding="utf-8")
    if os.name == "posix":
        secret_file.chmod(0o600)

    process_environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("MIGRATION_DB_") and key != "DATABASE_URL"
    }
    process_environment.update(
        {
            "MIGRATION_DB_HOST": parsed_url.host,
            "MIGRATION_DB_PORT": str(parsed_url.port or 3306),
            "MIGRATION_DB_NAME": "trend_leader_test",
            "MIGRATION_DB_USER": parsed_url.username,
            "MIGRATION_DB_PASSWORD_FILE": str(secret_file),
        }
    )

    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND_DIR,
            env=process_environment,
            check=True,
        )
    finally:
        secret_file.unlink(missing_ok=True)

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
