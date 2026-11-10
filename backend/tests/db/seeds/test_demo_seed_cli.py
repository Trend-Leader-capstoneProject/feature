"""CLI 초기화 단계도 실제 DB 접속 없이 안전하게 실패해야 한다."""

import builtins
import logging
import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from pymysql.err import OperationalError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core import config
from app.db.seeds import demo_trends
from app.models.trend import Trend
from scripts import seed_demo_trends as cli

SECRET = "fake-password-sentinel"
URL = f"mysql+pymysql://user:{SECRET}@unapproved.invalid:3307/private"


def settings():
    return SimpleNamespace(
        app_env="local",
        demo_seed_allowed_host="127.0.0.1",
        demo_seed_allowed_port=3307,
        demo_seed_allowed_database="trend_leader_test",
        demo_seed_allowed_current_user="seed_manager@%",
    )


@pytest.mark.parametrize(
    "stage",
    ["settings", "import", "url", "checkout", "seed", "close"],
)
def test_cli_catches_initialization_and_db_errors(monkeypatch, capsys, stage):
    fake_settings = settings()
    getter = Mock(return_value=fake_settings)
    monkeypatch.setattr(config, "get_settings", getter)
    factory = MagicMock()
    seed = Mock()
    monkeypatch.setattr(demo_trends, "seed_demo_trends", seed)
    original_import = builtins.__import__

    def import_module(name, *args, **kwargs):
        if name == "app.db.session":
            if stage == "import":
                raise RuntimeError(URL)
            if stage == "url":
                create_engine(f"malformed-{SECRET}")
            return SimpleNamespace(SessionLocal=factory, engine=Mock())
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_module)
    if stage == "settings":
        getter.side_effect = ValueError(URL)
    elif stage == "checkout":
        factory.return_value.__enter__.side_effect = RuntimeError(URL)
    elif stage == "seed":
        seed.side_effect = RuntimeError(URL)
    elif stage == "close":
        factory.return_value.__exit__.side_effect = RuntimeError(URL)

    assert cli.main() == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert "실패" in captured.err
    assert SECRET not in captured.err
    assert URL not in captured.err
    assert "Traceback" not in captured.err


def test_cli_delivers_independent_approval(monkeypatch, capsys):
    monkeypatch.setattr(config, "get_settings", settings)
    factory = MagicMock()
    monkeypatch.setitem(
        sys.modules,
        "app.db.session",
        SimpleNamespace(SessionLocal=factory, engine=Mock()),
    )
    seed = Mock()
    monkeypatch.setattr(demo_trends, "seed_demo_trends", seed)
    assert cli.main() == 0
    seed.assert_called_once_with(
        factory.return_value.__enter__.return_value,
        app_env="local",
        allowed_host="127.0.0.1",
        allowed_port=3307,
        allowed_database="trend_leader_test",
        allowed_current_user="seed_manager@%",
    )
    assert "완료" in capsys.readouterr().out


@pytest.mark.parametrize("failure", ["url", "settings"])
def test_module_exit_does_not_print_raw_errors(failure):
    environment = os.environ.copy()
    environment.update(
        DEBUG="false",
        JWT_SECRET_KEY="fake-test-secret-key-at-least-32-characters",
        DATABASE_URL=f"malformed-{SECRET}",
        DEMO_SEED_ALLOWED_HOST="127.0.0.1",
        DEMO_SEED_ALLOWED_PORT="3307" if failure == "url" else SECRET,
        DEMO_SEED_ALLOWED_DATABASE="trend_leader_test",
        DEMO_SEED_ALLOWED_CURRENT_USER="seed_manager@%",
    )
    result = subprocess.run(
        [sys.executable, "-m", "scripts.seed_demo_trends"],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 1
    assert SECRET not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert not result.stdout


def test_api_settings_allow_missing_approval(monkeypatch):
    for key in ("HOST", "PORT", "DATABASE", "CURRENT_USER"):
        monkeypatch.delenv(f"DEMO_SEED_ALLOWED_{key}", raising=False)
    value = config.Settings(
        _env_file=None,
        debug=False,
        jwt_secret_key="fake-secret-key-at-least-32-characters",
    )
    assert value.demo_seed_allowed_host is None
    assert value.demo_seed_allowed_port is None
    assert value.demo_seed_allowed_database is None
    assert value.demo_seed_allowed_current_user is None


def test_database_url_retains_priority(monkeypatch):
    value = config.Settings(
        _env_file=None,
        debug=False,
        jwt_secret_key="fake-secret-key-at-least-32-characters",
        database_url=URL,
        db_host="127.0.0.1",
        db_port=3307,
        demo_seed_allowed_host="127.0.0.1",
        demo_seed_allowed_port=3307,
    )
    assert value.sync_database_url == URL
    assert value.demo_seed_allowed_host == "127.0.0.1"
    engine = create_engine(value.sync_database_url)
    checkout = Mock(side_effect=AssertionError("checkout"))
    monkeypatch.setattr(engine, "connect", checkout)
    with Session(engine) as db:
        flush = Mock(wraps=db.flush)
        commit = Mock(wraps=db.commit)
        monkeypatch.setattr(db, "flush", flush)
        monkeypatch.setattr(db, "commit", commit)
        with pytest.raises(demo_trends.DemoTrendSeedError, match="connection_target"):
            demo_trends.seed_demo_trends(
                db,
                app_env="local",
                allowed_host=value.demo_seed_allowed_host,
                allowed_port=value.demo_seed_allowed_port,
                allowed_database="trend_leader_test",
                allowed_current_user="seed_manager@%",
            )
        flush.assert_not_called()
        commit.assert_not_called()
    checkout.assert_not_called()
    engine.dispose()


@pytest.mark.parametrize("failure", ["rollback", "reset", "close", "success"])
def test_cli_sanitizes_real_pool_cleanup_errors(monkeypatch, capsys, caplog, failure):
    """모의 DBAPI지만 Session/Pool의 Rollback·reset·invalidate는 실제 경로다."""
    dbapi = Mock(name=URL)
    cursor = Mock()
    dbapi.character_set_name.return_value = "utf8mb4"
    dbapi.cursor.return_value = cursor
    cursor.description = [
        (name, None, None, None, None, None, None)
        for name in ("db_name", "authenticated_user")
    ]
    cursor.fetchall.return_value = [("trend_leader_test", "seed_manager@%")]
    cursor.fetchone.side_effect = [("trend_leader_test", "seed_manager@%"), None]
    cursor.lastrowid = 101
    cursor.rowcount = 1

    def execute(statement, parameters=None):
        if statement.startswith("INSERT"):
            cursor.description = None

    cursor.execute.side_effect = execute
    fail_cleanup = False

    def rollback():
        if fail_cleanup:
            raise OperationalError(9999, f"{SECRET} {URL}")

    dbapi.rollback.side_effect = rollback
    if failure == "close":
        dbapi.close.side_effect = OperationalError(9998, f"{SECRET} {URL}")
    engine = create_engine(
        "mysql+pymysql://fake@127.0.0.1:3307/trend_leader_test",
        creator=lambda: dbapi,
    )
    engine.dialect.initialize = Mock()
    engine.dialect.server_version_info = (10, 11, 0)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    session.rollback = Mock(wraps=session.rollback)
    session.close = Mock(wraps=session.close)
    original_engine_logger = engine.logger
    original_pool_logger = engine.pool.logger
    stderr_handler = logging.StreamHandler()
    original_pool_logger.addHandler(stderr_handler)
    monkeypatch.setattr(config, "get_settings", settings)
    monkeypatch.setitem(
        sys.modules, "app.db.session",
        SimpleNamespace(SessionLocal=lambda: session, engine=engine),
    )

    def rows(db):
        nonlocal fail_cleanup
        if failure == "success":
            db.add(Trend(title="test", normalized_title="cli-pool-success"))
            db.flush()
            return
        fail_cleanup = True
        if failure != "reset":
            raise RuntimeError("synthetic seed failure")

    monkeypatch.setattr(demo_trends, "_seed_demo_rows", rows)
    try:
        assert cli.main() == (0 if failure == "success" else 1)
        assert dbapi.rollback.call_count >= 2  # 원래 Rollback/reset 시도 유지
        if failure == "success":
            dbapi.close.assert_not_called()
            dbapi.commit.assert_called_once()
        else:
            dbapi.close.assert_called_once()  # 실패 연결은 Pool에서 무효화·종료
        if failure in {"rollback", "close"}:
            session.rollback.assert_called_once()
        else:
            session.rollback.assert_not_called()
        session.close.assert_called_once()
        assert not session.in_transaction()
        assert engine.pool.checkedout() == 0
        assert engine.logger is original_engine_logger
        assert engine.pool.logger is original_pool_logger
        records = [r for r in caplog.records if r.name.startswith("sqlalchemy.pool")]
        assert any(r.levelno >= logging.ERROR for r in records) == (
            failure != "success"
        )
        captured = capsys.readouterr()
        combined = captured.out + captured.err + caplog.text
        assert SECRET not in combined
        assert URL not in combined
        assert "OperationalError" not in combined
        assert "Traceback" not in combined
        if failure == "success":
            assert "완료" in captured.out
            assert not captured.err
        else:
            assert "완료" not in captured.out
            assert "실패" in captured.err
        assert all(r.exc_info is None and not r.exc_text for r in records)
        logging.getLogger("demo_seed_unrelated_test").warning("unrelated marker")
        assert "unrelated marker" in caplog.text
    finally:
        fail_cleanup = False
        dbapi.close.side_effect = None
        original_pool_logger.removeHandler(stderr_handler)
        engine.dispose()
