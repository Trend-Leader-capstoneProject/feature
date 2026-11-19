"""Exercise env.py with mocked Alembic execution; no DB or revisions run."""

import runpy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
import sqlalchemy
from alembic.config import Config
from sqlalchemy.engine import URL, Connection

from alembic import context
from app.core import migration_db_config
from app.db.base import Base

ENV_PATH = Path(__file__).resolve().parents[2] / "alembic" / "env.py"


@pytest.fixture
def environment(monkeypatch):
    config = Config()
    settings = SimpleNamespace(
        connection_url=URL.create(
            "mysql+pymysql",
            username="migration",
            password="test-only-password",
            host="unused.invalid",
            database="unused",
        ),
        connection_timeout=7,
    )
    settings_factory = Mock(return_value=settings)
    monkeypatch.setattr(migration_db_config, "MigrationDbSettings", settings_factory)
    monkeypatch.setattr(context, "config", config, raising=False)
    monkeypatch.setattr(context, "is_offline_mode", Mock(return_value=False))
    configure = Mock()
    transaction = MagicMock()
    begin = Mock(return_value=transaction)
    run = Mock()
    monkeypatch.setattr(context, "configure", configure)
    monkeypatch.setattr(context, "begin_transaction", begin)
    monkeypatch.setattr(context, "run_migrations", run)
    engine = MagicMock()
    factory = Mock(return_value=engine)
    monkeypatch.setattr(sqlalchemy, "create_engine", factory)
    return SimpleNamespace(
        config=config,
        settings=settings,
        settings_factory=settings_factory,
        configure=configure,
        begin=begin,
        transaction=transaction,
        run=run,
        engine=engine,
        factory=factory,
    )


def assert_online_context(environment, connection):
    environment.configure.assert_called_once_with(
        connection=connection,
        transaction_per_migration=True,
        target_metadata=Base.metadata,
        compare_type=True,
        compare_server_default=False,
        include_schemas=False,
    )
    assert environment.configure.call_args.kwargs["connection"] is connection
    environment.begin.assert_called_once_with()
    environment.transaction.__enter__.assert_called_once_with()
    environment.run.assert_called_once_with()
    environment.transaction.__exit__.assert_called_once()
    environment.settings_factory.assert_called_once_with(_env_file=None)


@pytest.mark.parametrize("fails", [False, True])
def test_external_connection_is_reused_and_remains_caller_owned(environment, fails):
    connection = MagicMock(spec=Connection)
    environment.config.attributes["connection"] = connection
    # Reusing the connection must not read a secret or construct a new URL.
    del environment.settings.connection_url
    if fails:
        environment.run.side_effect = RuntimeError("migration failed")
        with pytest.raises(RuntimeError, match="migration failed"):
            runpy.run_path(str(ENV_PATH))
    else:
        runpy.run_path(str(ENV_PATH))

    assert_online_context(environment, connection)
    environment.factory.assert_not_called()
    assert connection.mock_calls == []
    assert environment.config.attributes["connection"] is connection


@pytest.mark.parametrize("explicit_none", [False, True])
@pytest.mark.parametrize("fails", [False, True])
def test_without_external_connection_preserves_engine_path(
    environment, explicit_none, fails
):
    if explicit_none:
        environment.config.attributes["connection"] = None
    if fails:
        environment.run.side_effect = RuntimeError("migration failed")
        with pytest.raises(RuntimeError, match="migration failed"):
            runpy.run_path(str(ENV_PATH))
    else:
        runpy.run_path(str(ENV_PATH))

    environment.factory.assert_called_once_with(
        environment.settings.connection_url,
        poolclass=sqlalchemy.pool.NullPool,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 7, "charset": "utf8mb4"},
    )
    environment.engine.connect.assert_called_once_with()
    manager = environment.engine.connect.return_value
    manager.__enter__.assert_called_once_with()
    assert_online_context(environment, manager.__enter__.return_value)
    manager.__exit__.assert_called_once()


@pytest.mark.parametrize("external", [False, True])
def test_offline_mode_preserves_url_options_and_never_uses_connection(
    environment, monkeypatch, external
):
    connection = MagicMock(spec=Connection)
    if external:
        environment.config.attributes["connection"] = connection
    monkeypatch.setattr(context, "is_offline_mode", Mock(return_value=True))
    runpy.run_path(str(ENV_PATH))

    environment.configure.assert_called_once_with(
        url=environment.settings.connection_url.set(password=None).render_as_string(
            hide_password=True
        ),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        target_metadata=Base.metadata,
        compare_type=True,
        compare_server_default=False,
        include_schemas=False,
    )
    environment.run.assert_called_once_with()
    environment.factory.assert_not_called()
    assert connection.mock_calls == []
