"""Offline B-2 observation contract: never use the MariaDB fixtures."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.migration_db_config import MigrationDbSettings
from scripts import migration_observation as observation


@pytest.fixture
def settings(tmp_path):
    secret = tmp_path / "password"
    secret.write_text("test-secret-marker", encoding="utf-8")
    return MigrationDbSettings(
        host="db",
        port=3306,
        name="trend",
        user="migrator",
        password_file=secret,
    )


class FakeConnection:
    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail
        self.target = ("trend", "migrator@%", "12.3.2-MariaDB")
        self.defaults = [("utf8mb4", "utf8mb4_unicode_ci")]
        self.objects = [("TABLE", "alembic_version"), ("TABLE", "users")]
        self.revisions = [("a4d7c9e21f3b",)]

    def step(self, name):
        self.calls.append(name)
        if name == self.fail:
            raise RuntimeError("test-secret-marker mysql://user:password@host")

    def exec_driver_sql(self, sql):
        self.step(sql)
        assert sql in observation.ALLOWED_SQL
        rows = {
            observation.START_READ_ONLY: [],
            observation.TARGET_SQL: [self.target],
            observation.DEFAULTS_SQL: self.defaults,
            observation.OBJECTS_SQL: self.objects,
            observation.REVISIONS_SQL: self.revisions,
        }[sql]
        return SimpleNamespace(
            fetchall=lambda: rows, close=lambda: self.step("result.close")
        )

    def rollback(self):
        self.step("rollback")

    def close(self):
        self.step("close")


def run(monkeypatch, settings, connection=None, fail=None):
    connection = connection or FakeConnection(fail)
    engine = Mock()
    engine.pool.cleanup_failed = False
    engine.connect.side_effect = lambda: connection
    factory = Mock(return_value=engine)
    monkeypatch.setattr(observation, "create_engine", factory)
    result = observation.observe_database(settings)
    return result, connection, engine, factory


def test_single_connection_read_only_first_and_cleanup(monkeypatch, settings):
    result, connection, engine, factory = run(monkeypatch, settings)
    assert result.schema_state == "VERSIONED_OBSERVED"
    assert result.reason_codes == ()
    assert result.current_revisions == ("a4d7c9e21f3b",)
    assert result.observed_target.database == "trend"
    assert result.observed_target.current_user == "migrator@%"
    assert result.observed_target.database_charset == "utf8mb4"
    sql = [call for call in connection.calls if call in observation.ALLOWED_SQL]
    assert sql == list(observation.ALLOWED_SQL)
    assert connection.calls[0] == "START TRANSACTION READ ONLY"
    assert connection.calls[-2:] == ["rollback", "close"]
    engine.connect.assert_called_once_with()
    engine.dispose.assert_called_once_with()
    options = factory.call_args.kwargs
    assert options["pool_pre_ping"] is False
    assert options["hide_parameters"] is True
    assert options["connect_args"]["connect_timeout"] == 5
    assert options["connect_args"]["autocommit"] is False


@pytest.mark.parametrize(
    ("objects", "revisions", "state"),
    [
        ([], [], "UNVERSIONED_EMPTY_CANDIDATE"),
        ([("ROUTINE", "proc")], [], "INDETERMINATE"),
        ([("EVENT", "job")], [], "INDETERMINATE"),
        ([("TRIGGER", "trigger")], [], "INDETERMINATE"),
        ([("VIEW", "alembic_version")], [], "INDETERMINATE"),
        ([("TABLE", "alembic_version")], [], "INDETERMINATE"),
        ([("TABLE", "alembic_version")], [("unknown",)], "INDETERMINATE"),
        ([("TABLE", "alembic_version")], [(None,)], "INDETERMINATE"),
        (
            [("TABLE", "alembic_version")],
            [("2f29fa23597c",), ("a4d7c9e21f3b",)],
            "INDETERMINATE",
        ),
    ],
)
def test_schema_observations(monkeypatch, settings, objects, revisions, state):
    connection = FakeConnection()
    connection.objects, connection.revisions = objects, revisions
    result, connection, _, _ = run(monkeypatch, settings, connection)
    assert result.schema_state == state
    assert result.reason_codes == (
        () if state != "INDETERMINATE" else ("SCHEMA_INDETERMINATE",)
    )
    if ("TABLE", "alembic_version") not in objects:
        assert observation.REVISIONS_SQL not in connection.calls


@pytest.mark.parametrize(
    ("target", "reason"),
    [
        (("other", "migrator@%", "12.3.2-MariaDB"), "TARGET_MISMATCH"),
        (("trend", "root@localhost", "12.3.2-MariaDB"), "TARGET_MISMATCH"),
        ((None, "migrator@%", "12.3.2-MariaDB"), "OBSERVATION_FAILED"),
        (("trend", "", "12.3.2-MariaDB"), "OBSERVATION_FAILED"),
        (("trend", "migrator", "12.3.2-MariaDB"), "OBSERVATION_FAILED"),
        (("trend", "migrator@%", "8.4.0"), "OBSERVATION_FAILED"),
    ],
)
def test_invalid_or_mismatched_target_fails_closed(
    monkeypatch, settings, target, reason
):
    connection = FakeConnection()
    connection.target = target
    result, connection, _, _ = run(monkeypatch, settings, connection)
    assert result.reason_codes == (reason,)
    assert result.schema_state is None
    assert observation.REVISIONS_SQL not in connection.calls


@pytest.mark.parametrize(
    "failure",
    [
        "START TRANSACTION READ ONLY",
        "SELECT DATABASE(), CURRENT_USER(), VERSION()",
        "defaults",
        "objects",
        "revisions",
        "result.close",
        "rollback",
        "close",
        "connect",
        "dispose",
    ],
)
def test_failures_are_sanitized_no_retry_and_cleanup_attempted(
    monkeypatch, settings, capsys, caplog, failure
):
    failure = {
        "defaults": observation.DEFAULTS_SQL,
        "objects": observation.OBJECTS_SQL,
        "revisions": observation.REVISIONS_SQL,
    }.get(failure, failure)
    connection = FakeConnection(failure)
    engine = Mock()
    engine.pool.cleanup_failed = False
    engine.connect.return_value = connection
    if failure in ("connect", "dispose"):
        getattr(engine, failure).side_effect = RuntimeError("test-secret-marker")
    factory = Mock(return_value=engine)
    monkeypatch.setattr(observation, "create_engine", factory)
    result = observation.observe_database(settings)
    assert result.schema_state is None
    expected = (
        "DB_CONNECTION_FAILED"
        if failure == "connect"
        else "READ_ONLY_NOT_ESTABLISHED"
        if failure in (observation.START_READ_ONLY, "result.close")
        else "OBSERVATION_FAILED"
    )
    assert expected in result.reason_codes
    engine.connect.assert_called_once_with()
    engine.dispose.assert_called_once_with()
    if failure != "connect":
        assert connection.calls[-2:] == ["rollback", "close"]
    if failure == observation.START_READ_ONLY:
        assert observation.TARGET_SQL not in connection.calls
    assert "test-secret-marker" not in repr(result) + caplog.text + str(
        capsys.readouterr()
    )


def test_invalid_secret_never_creates_engine(monkeypatch, settings):
    settings.password_file = settings.password_file.parent / "missing"
    result, _, engine, factory = run(monkeypatch, settings)
    assert result.reason_codes == ("SETTINGS_INVALID",)
    factory.assert_not_called()
    engine.connect.assert_not_called()


@pytest.mark.parametrize(
    "defaults", [[], [(None, "collation")], [("a", "b"), ("c", "d")]]
)
def test_missing_or_ambiguous_defaults_fail_closed(monkeypatch, settings, defaults):
    connection = FakeConnection()
    connection.defaults = defaults
    result, connection, _, _ = run(monkeypatch, settings, connection)
    assert result.reason_codes == ("OBSERVATION_FAILED",)
    assert observation.OBJECTS_SQL not in connection.calls


def test_arbitrary_sql_is_rejected_before_execution():
    connection = Mock()
    with pytest.raises(ValueError):
        observation._rows(connection, "SELECT GET_LOCK('db', 1)")
    connection.exec_driver_sql.assert_not_called()


def test_null_revision_is_preserved_as_indeterminate(monkeypatch, settings):
    connection = FakeConnection()
    connection.revisions = [(None,)]
    result, _, _, _ = run(monkeypatch, settings, connection)
    assert result.current_revisions == (None,)
    assert result.schema_state == "INDETERMINATE"


@pytest.mark.parametrize("failure", ["factory", "lineage"])
def test_setup_failures_are_sanitized(monkeypatch, settings, failure, caplog, capsys):
    factory = Mock(side_effect=RuntimeError("test-secret-marker"))
    monkeypatch.setattr(observation, "create_engine", factory)
    if failure == "lineage":
        monkeypatch.setattr(observation, "repository_revisions", factory)
    result = observation.observe_database(settings)
    expected = "OBSERVATION_FAILED" if failure == "lineage" else "DB_CONNECTION_FAILED"
    assert result.reason_codes == (expected,)
    assert "test-secret-marker" not in repr(result) + caplog.text + str(
        capsys.readouterr()
    )


@pytest.mark.parametrize("failure", [None, "disconnect", "rollback", "close"])
def test_real_sqlalchemy_with_fake_dbapi_never_reconnects(
    monkeypatch, settings, failure, caplog, capsys
):
    """Real dialect/autobegin/pool, fake wire; NOT MariaDB validation."""
    import pymysql
    from sqlalchemy import create_engine

    calls = []
    identities = []
    fixture = FakeConnection()

    class Cursor:
        rowcount = -1
        description = None

        def execute(self, sql, parameters=None):
            calls.append(sql)
            identities.append(id(driver))
            if sql == observation.TARGET_SQL and failure == "disconnect":
                raise pymysql.err.OperationalError(2013, "test-secret-marker")
            self.rows = {
                "SET NAMES utf8mb4": [],
                observation.START_READ_ONLY: [],
                observation.TARGET_SQL: [fixture.target],
                observation.DEFAULTS_SQL: fixture.defaults,
                observation.OBJECTS_SQL: fixture.objects,
                observation.REVISIONS_SQL: fixture.revisions,
            }[sql]
            self.description = (
                [
                    (f"column_{index}", None, None, None, None, None, None)
                    for index in range(len(self.rows[0]))
                ]
                if self.rows
                else None
            )

        def fetchall(self):
            return self.rows

        def close(self):
            pass

    class Driver:
        def character_set_name(self):
            return "utf8mb4"

        def cursor(self):
            return Cursor()

        def rollback(self):
            calls.append("rollback")
            # The dialect performs one initialization rollback before app SQL.
            if failure == "rollback" and observation.START_READ_ONLY in calls:
                raise pymysql.err.OperationalError(2013, "test-secret-marker")

        def close(self):
            calls.append("close")
            if failure == "close":
                raise RuntimeError("test-secret-marker")

    driver = Driver()
    creator = Mock(return_value=driver)
    connections = []

    def factory(url, **kwargs):
        engine = create_engine(url, creator=creator, **kwargs)
        # No server: skip dialect discovery only. Keep real on_connect SET
        # NAMES, autobegin, do_begin, error invalidation, rollback and pool close.
        engine.dialect.initialize = lambda connection: None
        from sqlalchemy import event

        event.listen(
            engine,
            "before_cursor_execute",
            lambda conn, *args: connections.append(id(conn)),
        )
        return engine

    monkeypatch.setattr(observation, "create_engine", factory)
    result = observation.observe_database(settings)
    creator.assert_called_once_with()
    assert len(set(identities)) == 1
    assert len(set(connections)) == 1
    app_sql = [
        call for call in calls if call not in ("SET NAMES utf8mb4", "rollback", "close")
    ]
    assert app_sql[0] == "START TRANSACTION READ ONLY"
    assert all(sql in observation.ALLOWED_SQL for sql in app_sql)
    assert calls.count("close") == 1
    if failure:
        assert result.schema_state is None
        assert result.reason_codes == ("OBSERVATION_FAILED",)
    else:
        assert result.schema_state == "VERSIONED_OBSERVED"
        assert app_sql == list(observation.ALLOWED_SQL)
    if failure == "disconnect":
        assert app_sql == [observation.START_READ_ONLY, observation.TARGET_SQL]
    assert "test-secret-marker" not in repr(result) + caplog.text + str(
        capsys.readouterr()
    )


def test_installed_pymysql_query_does_not_reconnect(monkeypatch):
    import pymysql

    driver = pymysql.connections.Connection(defer_connect=True)
    reconnect = Mock(side_effect=AssertionError("reconnected"))
    monkeypatch.setattr(driver, "connect", reconnect)
    with pytest.raises(pymysql.err.InterfaceError):
        driver.query(observation.TARGET_SQL)
    reconnect.assert_not_called()


def test_repository_lineage_is_loaded_without_alembic_env():
    assert observation.repository_revisions() == frozenset(
        {
            "2f29fa23597c",
            "7e9d740c5df1",
            "a4d7c9e21f3b",
        }
    )
