"""Guard APPLY orchestration contracts; synthetic review facts, no live DB."""

import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import sqlalchemy

from app.core.migration_db_config import MigrationDbSettings
from scripts import migration_apply as apply
from scripts.migration_apply_audit import AuditRejected
from scripts.migration_approval import ComparisonContext, RecoveryConfirmation
from scripts.migration_guard import main
from scripts.migration_observation import (
    DEFAULTS_SQL,
    OBJECTS_SQL,
    REVISIONS_SQL,
    TARGET_SQL,
)

NOW = datetime(2026, 11, 17, 3, tzinfo=UTC)
DIGEST = "sha256:" + "a" * 64
SENSITIVE = "sensitive-marker mysql://user:password@host JWT"


class Result:
    def __init__(self, rows):
        self.rows = rows
        self.closed = False

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True


class Connection:
    """Exercise the actual catalog checks, not a mocked _check_live."""

    def __init__(self):
        self.revision = "a4d7c9e21f3b"
        self.database = "trend"
        self.account = "migrator@%"
        self.collation = "utf8mb4_unicode_ci"
        self.charset = "utf8mb4"
        self.session = 17
        self.lock_owner = None
        self.lock_result = 1
        self.release_result = 1
        self.invalidated = False
        self.closed = False
        self.history = []
        self.results = []
        self.on_lock = lambda: None
        self.fail_sql = None
        self.commit = Mock(side_effect=lambda: self.history.append("COMMIT"))

    def exec_driver_sql(self, sql, parameters=()):
        assert not self.closed
        self.history.append((sql, parameters))
        if sql == self.fail_sql:
            raise RuntimeError(SENSITIVE)
        if sql == apply.SESSION_ID:
            rows = [(self.session,)]
        elif sql == apply.GET_LOCK:
            self.on_lock()
            if self.lock_result == 1:
                self.lock_owner = self.session
            rows = [(self.lock_result,)]
        elif sql == apply.LOCK_OWNER:
            rows = [(self.lock_owner,)]
        elif sql == apply.RELEASE_LOCK:
            self.lock_owner = None
            rows = [(self.release_result,)]
        elif sql == TARGET_SQL:
            rows = [(self.database, self.account, "12.3.2-MariaDB")]
        elif sql == DEFAULTS_SQL:
            rows = [(self.charset, self.collation)]
        elif sql == OBJECTS_SQL:
            rows = ([] if self.revision is None else
                    [("TABLE", "alembic_version"), ("TABLE", "users")])
        elif sql == REVISIONS_SQL:
            rows = [(self.revision,)]
        elif sql in apply.SCHEMA_SQL:
            rows = ([] if self.revision is None else
                    [("before" if self.revision == "a4d7c9e21f3b" else "after",)])
        elif sql == "SHOW GRANTS":
            rows = [("synthetic independently reviewed grants",)]
        else:
            raise AssertionError("unexpected SQL")
        result = Result(rows)
        self.results.append(result)
        return result

    def close(self):
        self.history.append("CLOSE")
        self.closed = True


@pytest.fixture
def harness(tmp_path, monkeypatch):
    # Explicit synthetic review context; this never supplies production trust.
    monkeypatch.setattr(os, "environ", {})
    secret = tmp_path / "credential"
    secret.write_text("synthetic-password", encoding="utf-8")
    manifest = {
        "schema_version": 1, "approval_id": "approval-001",
        "environment": "isolated-test", "deployment_project": "apply-test",
        "db_host": "db", "db_port": 3306, "db_name": "trend",
        "expected_db_account": "migrator@%",
        "expected_from_revision": "a4d7c9e21f3b",
        "target_revision": "b7f2c81d9e04",
        "backend_image_digest": DIGEST,
        "preflight_evidence_id": "c66363da-35db-41ac-9748-20c0a2e76bca",
        "backup_or_empty_db_evidence_id": "recovery-001",
        "approved_by": "operator-001", "approved_at": "2026-11-17T02:00:00Z",
        "expires_at": "2026-11-17T04:00:00Z",
    }
    evidence = {
        "schema_version": 1, "evidence_id": manifest["preflight_evidence_id"],
        "observed_at_utc": "2026-11-17T01:00:00Z",
        "inspection_status": "OBSERVED", "schema_state": "VERSIONED_OBSERVED",
        "configured_target": {
            "host": "db", "port": 3306, "database": "trend", "user": "migrator",
        },
        "observed_target": {
            "database": "trend", "current_user": "migrator@%",
            "server_version": "12.3.2-MariaDB", "database_charset": "utf8mb4",
            "database_collation": "utf8mb4_unicode_ci",
        },
        "current_revisions": ["a4d7c9e21f3b"], "reason_codes": [],
        "checks": {"version_table_visible": True, "business_objects_visible": True},
        "image_identity_verification_status": "NOT_VERIFIED",
    }
    payload = json.dumps(manifest).encode()
    observed = json.dumps(evidence).encode()
    manifest_pin = apply.sha256(payload).hexdigest()
    context = ComparisonContext(
        "isolated-test", "apply-test", manifest_pin,
        apply.sha256(observed).hexdigest(), DIGEST, frozenset(),
        RecoveryConfirmation("recovery-001", "BACKUP_RESTORE", manifest_pin),
    )
    connection = Connection()
    before = apply.schema_fingerprint(connection)
    grants = apply.grants_fingerprint(connection)
    connection.revision = "b7f2c81d9e04"
    after = apply.schema_fingerprint(connection)
    connection.revision = "a4d7c9e21f3b"
    connection.history.clear()
    audit = Mock()
    audit.consume.return_value = "synthetic-claim"
    engine = SimpleNamespace(
        connect=Mock(return_value=connection), dispose=Mock(),
        pool=SimpleNamespace(cleanup_failed=False),
    )
    factory = Mock(return_value=engine)
    listeners = {}
    monkeypatch.setattr(apply, "create_engine", factory)
    monkeypatch.setattr(
        apply.event, "listen", lambda e, key, fn: listeners.update({key: fn}))

    def upgrade(conn, revision):
        assert conn is connection
        assert connection.lock_owner == connection.session
        assert connection.history[-1] == "COMMIT"
        connection.revision = revision

    upgrader = Mock(side_effect=upgrade)
    monkeypatch.setattr(apply, "_upgrade", upgrader)
    request = apply.ApplyRequest(
        payload, observed, context,
        MigrationDbSettings(host="db", port=3306, name="trend", user="migrator",
                            password_file=secret),
        audit, before, after, grants,
    )
    return SimpleNamespace(
        request=request, connection=connection, audit=audit, engine=engine,
        factory=factory, upgrader=upgrader, listeners=listeners,
        run=lambda req=None, **kw: apply.run_authorized_apply(
            req or request, clock=kw.get("clock", lambda: NOW)),
    )


def test_no_operational_adapter_means_no_apply(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("DB must not be reached")

    monkeypatch.setattr(apply, "create_engine", forbidden)
    assert apply.run_apply() == (2, ("MODE_NOT_ENABLED",))


def test_success_consumes_before_connect_and_uses_one_locked_connection(harness):
    h = harness
    h.engine.connect.side_effect = lambda: (
        h.audit.consume.assert_called_once() or h.connection)
    assert h.run() == (0, ("APPLIED",))
    h.audit.consume.assert_called_once_with(
        "approval-001", manifest_sha256=h.request.context.manifest_sha256,
        evidence_sha256=h.request.context.evidence_sha256,
    )
    h.upgrader.assert_called_once_with(h.connection, "b7f2c81d9e04")
    h.engine.connect.assert_called_once()
    h.audit.finish.assert_called_once_with("synthetic-claim", "APPLIED", "APPLIED")
    assert h.connection.closed
    assert all(result.closed for result in h.connection.results)
    h.engine.dispose.assert_called_once()
    assert h.factory.call_args.kwargs["pool_pre_ping"] is False
    assert h.factory.call_args.kwargs["echo"] is False
    assert h.factory.call_args.kwargs["hide_parameters"] is True
    queries = [x[0] for x in h.connection.history if isinstance(x, tuple)]
    assert queries.count(TARGET_SQL) == 3
    assert queries.count(apply.GET_LOCK) == queries.count(apply.RELEASE_LOCK) == 1


@pytest.mark.parametrize("field", [
    "manifest_sha256", "evidence_sha256", "verified_image_digest", "recovery",
    "used_approval_ids",
])
def test_missing_independent_review_never_consumes_or_connects(harness, field):
    h = harness
    req = replace(h.request, context=replace(h.request.context, **{field: None}))
    assert h.run(req)[0] == 2
    h.audit.consume.assert_not_called()
    h.factory.assert_not_called()


@pytest.mark.parametrize("key", [
    "DATABASE_URL", "DB_USER", "API_DB_USER", "JWT_SECRET_KEY",
    "MARIADB_ROOT_PASSWORD", "MIGRATION_DB_PASSWORD", "MIGRATION_DB_OTHER",
])
def test_runtime_environment_conflicts_block_before_access(harness, monkeypatch, key):
    monkeypatch.setattr(os, "environ", {key: ""})
    assert harness.run() == (2, ("ENV_CONFLICT",))
    harness.audit.consume.assert_not_called()
    harness.factory.assert_not_called()


@pytest.mark.parametrize("reason", ["AUDIT_WRITE_FAILED", "APPROVAL_ALREADY_USED"])
def test_atomic_consumption_failure_never_connects(harness, reason):
    h = harness
    h.audit.consume.side_effect = AuditRejected(reason)
    assert h.run() == (2 if reason == "APPROVAL_ALREADY_USED" else 4, (reason,))
    h.factory.assert_not_called()
    h.upgrader.assert_not_called()
    h.audit.finish.assert_not_called()


@pytest.mark.parametrize("value", [0, None, True, "1"])
def test_only_integer_one_acquires_lock(harness, value):
    h = harness
    h.connection.lock_result = value
    assert h.run() == (4, ("LOCK_NOT_ACQUIRED",))
    h.upgrader.assert_not_called()


@pytest.mark.parametrize(("field", "value"), [
    ("database", "other"), ("account", "migrator@localhost"),
    ("charset", "latin1"), ("collation", "utf8mb4_bin"),
    ("revision", "7e9d740c5df1"), ("revision", None),
])
@pytest.mark.parametrize("during_lock", [False, True])
def test_live_mismatch_before_or_after_wait_never_upgrades(
    harness, field, value, during_lock,
):
    h = harness
    def mutate():
        setattr(h.connection, field, value)
    if during_lock:
        h.connection.on_lock = mutate
    else:
        mutate()
    assert h.run() == (4, ("LIVE_CHECK_FAILED",))
    h.upgrader.assert_not_called()
    h.audit.finish.assert_called_once_with(
        "synthetic-claim", "FAILED", "LIVE_CHECK_FAILED")


@pytest.mark.parametrize("field", [
    "before_schema_sha256", "after_schema_sha256", "grants_sha256",
])
def test_exact_reviewed_schema_and_privileges_required(harness, field):
    h = harness
    result = h.run(replace(h.request, **{field: "0" * 64}))
    assert result[0] == 4
    if field != "after_schema_sha256":
        h.upgrader.assert_not_called()
    else:
        h.audit.finish.assert_called_once_with(
            "synthetic-claim", "UNKNOWN", "LIVE_CHECK_FAILED")


def test_expiration_during_lock_wait_blocks_apply(harness):
    times = iter([NOW, NOW + timedelta(hours=1)])
    assert harness.run(clock=lambda: next(times)) == (4, ("APPROVAL_TIME_INVALID",))
    harness.upgrader.assert_not_called()


@pytest.mark.parametrize("failure", [RuntimeError(SENSITIVE), KeyboardInterrupt()])
def test_ddl_exception_is_unknown_without_retry(harness, failure, capsys, caplog):
    h = harness
    h.upgrader.side_effect = failure
    assert h.run() == (4, ("APPLY_OUTCOME_UNKNOWN",))
    h.upgrader.assert_called_once()
    h.engine.connect.assert_called_once()
    h.audit.finish.assert_called_once_with(
        "synthetic-claim", "UNKNOWN", "APPLY_OUTCOME_UNKNOWN")
    assert SENSITIVE not in caplog.text + str(capsys.readouterr())


def test_post_revision_mismatch_is_unknown(harness):
    h = harness
    h.upgrader.side_effect = lambda *args: None
    assert h.run() == (4, ("LIVE_CHECK_FAILED",))
    assert h.audit.finish.call_args.args[1] == "UNKNOWN"


def test_reconnection_blocked_at_dbapi_creator_even_after_rollback(harness):
    h = harness

    def connect():
        h.listeners["do_connect"](None, None, (), {})
        return h.connection

    h.engine.connect.side_effect = connect

    def lost(*args):
        h.listeners["handle_error"](SimpleNamespace(is_disconnect=True))
        h.connection.invalidated = True
        # Simulate a code path trying SQLAlchemy's implicit reconnect.
        h.listeners["do_connect"](None, None, (), {})

    h.upgrader.side_effect = lost
    assert h.run()[0] == 4
    h.engine.connect.assert_called_once()
    h.upgrader.assert_called_once()
    assert not any(q[0] == apply.RELEASE_LOCK for q in h.connection.history
                   if isinstance(q, tuple))
    assert h.audit.finish.call_args.args[1] == "UNKNOWN"


@pytest.mark.parametrize("result", [0, None, True, "1"])
def test_release_failure_cannot_report_applied(harness, result):
    h = harness
    h.connection.release_result = result
    assert h.run() == (4, ("LOCK_RELEASE_FAILED",))
    h.audit.finish.assert_called_once_with(
        "synthetic-claim", "UNKNOWN", "LOCK_RELEASE_FAILED")


def test_lost_lock_cannot_report_applied(harness):
    h = harness

    def lost(*args):
        h.connection.revision = "b7f2c81d9e04"
        h.connection.lock_owner = 99

    h.upgrader.side_effect = lost
    assert h.run() == (4, ("LOCK_RELEASE_FAILED",))
    assert h.audit.finish.call_args.args[1] == "UNKNOWN"


@pytest.mark.parametrize("where", ["close", "dispose", "pool"])
def test_cleanup_failure_cannot_report_applied(harness, where):
    h = harness
    if where == "pool":
        h.engine.pool.cleanup_failed = True
    else:
        owner = h.connection if where == "close" else h.engine
        setattr(owner, where, Mock(side_effect=RuntimeError(SENSITIVE)))
    assert h.run() == (4, ("CLEANUP_FAILED",))
    assert h.audit.finish.call_args.args[1] == "UNKNOWN"


def test_final_journal_failure_never_returns_success_or_retries(harness):
    h = harness
    h.audit.finish.side_effect = RuntimeError(SENSITIVE)
    assert h.run() == (4, ("AUDIT_WRITE_FAILED",))
    h.upgrader.assert_called_once()
    h.audit.consume.assert_called_once()
    h.audit.finish.assert_called_once()


def test_connect_failure_consumes_id_but_never_retries(harness):
    h = harness
    h.engine.connect.side_effect = RuntimeError(SENSITIVE)
    assert h.run() == (4, ("DB_CONNECTION_FAILED",))
    h.engine.connect.assert_called_once()
    h.upgrader.assert_not_called()
    h.audit.finish.assert_called_once_with(
        "synthetic-claim", "FAILED", "DB_CONNECTION_FAILED")


def test_real_alembic_boundary_passes_exact_revision_and_connection(monkeypatch):
    upgrade = Mock()
    monkeypatch.setattr(apply.command, "upgrade", upgrade)
    connection = object()
    apply._upgrade(connection, "a4d7c9e21f3b")
    config, target = upgrade.call_args.args
    assert config.attributes["connection"] is connection
    assert target == "a4d7c9e21f3b"
    assert config.config_file_name is None
    assert config.get_main_option("sqlalchemy.url") is None


def test_guard_cannot_call_internal_executor(harness, monkeypatch, capsys):
    internal = Mock(side_effect=AssertionError("no operational trust adapter"))
    monkeypatch.setattr(apply, "run_authorized_apply", internal)
    assert main(["apply"]) == 2
    assert capsys.readouterr().err == "MODE_NOT_ENABLED\n"
    internal.assert_not_called()
    harness.audit.consume.assert_not_called()


def test_root_cannot_become_migration_account_even_with_matching_review(harness):
    h = harness
    manifest = json.loads(h.request.manifest)
    manifest["expected_db_account"] = "root@%"
    evidence = json.loads(h.request.evidence)
    evidence["configured_target"]["user"] = "root"
    evidence["observed_target"]["current_user"] = "root@%"
    payload, observed = json.dumps(manifest).encode(), json.dumps(evidence).encode()
    pin = apply.sha256(payload).hexdigest()
    context = replace(
        h.request.context, manifest_sha256=pin,
        evidence_sha256=apply.sha256(observed).hexdigest(),
        recovery=replace(h.request.context.recovery, manifest_sha256=pin),
    )
    h.connection.account = "root@%"
    settings = h.request.settings.model_copy(update={"user": "root"})
    req = replace(h.request, manifest=payload, evidence=observed,
                  context=context, settings=settings)
    assert h.run(req) == (2, ("APPLY_PREREQUISITES_INVALID",))
    h.audit.consume.assert_not_called()
    h.factory.assert_not_called()


def test_independently_reviewed_empty_bootstrap_uses_same_locked_path(harness):
    h = harness
    manifest = json.loads(h.request.manifest)
    manifest["expected_from_revision"] = None
    evidence = json.loads(h.request.evidence)
    evidence.update(current_revisions=[], schema_state="UNVERSIONED_EMPTY_CANDIDATE")
    evidence["checks"] = {
        "version_table_visible": False, "business_objects_visible": False,
    }
    payload, observed = json.dumps(manifest).encode(), json.dumps(evidence).encode()
    pin = apply.sha256(payload).hexdigest()
    context = replace(
        h.request.context, manifest_sha256=pin,
        evidence_sha256=apply.sha256(observed).hexdigest(),
        recovery=replace(h.request.context.recovery,
                         kind="EMPTY_BOOTSTRAP", manifest_sha256=pin),
    )
    h.connection.revision = None
    before = apply.schema_fingerprint(h.connection)
    req = replace(h.request, manifest=payload, evidence=observed, context=context,
                  before_schema_sha256=before)
    assert h.run(req) == (0, ("APPLIED",))
    h.upgrader.assert_called_once_with(h.connection, "b7f2c81d9e04")


def test_stale_unused_snapshot_cannot_replay_after_unknown_result(
    harness, tmp_path, monkeypatch,
):
    from scripts import migration_apply_audit as journal

    h = harness
    root = tmp_path / "journal"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(journal, "_sync_directory", lambda path: True)
    req = replace(h.request, audit=journal.FileApplyAudit(root))
    h.upgrader.side_effect = RuntimeError(SENSITIVE)
    assert h.run(req) == (4, ("APPLY_OUTCOME_UNKNOWN",))
    assert h.run(replace(req, audit=journal.FileApplyAudit(root))) == (
        2, ("APPROVAL_ALREADY_USED",))
    h.engine.connect.assert_called_once()
    h.upgrader.assert_called_once()
    record = next(root.glob("*/result.json"))
    assert json.loads(record.read_text())["status"] == "UNKNOWN"
    assert SENSITIVE not in record.read_text()


@pytest.mark.parametrize(("field", "value"), [
    ("lock_timeout", -1), ("lock_timeout", 31), ("lock_timeout", True),
    ("lock_timeout", "5"), ("before_schema_sha256", None),
    ("after_schema_sha256", "missing"), ("grants_sha256", ""),
])
def test_invalid_static_prerequisites_never_consume_or_connect(harness, field, value):
    h = harness
    assert h.run(replace(h.request, **{field: value}))[0] == 2
    h.audit.consume.assert_not_called()
    h.factory.assert_not_called()


def test_sqlalchemy_reconnect_after_invalidation_cannot_open_second_dbapi_connection():
    # Real SQLAlchemy event dispatch, with local in-memory SQLite, no MariaDB,
    # no L-2 lock test. This proves do_connect is the reconnection barrier.
    engine = sqlalchemy.create_engine("sqlite://", poolclass=apply._ObservationPool)
    state = apply._ConnectionState()
    sqlalchemy.event.listen(engine, "do_connect", state.connecting)
    physical_connections = []
    sqlalchemy.event.listen(
        engine, "connect", lambda *a: physical_connections.append(1))
    connection = engine.connect()
    try:
        connection.exec_driver_sql("SELECT 1").close()
        connection.invalidate()
        connection.rollback()
        with pytest.raises(sqlalchemy.exc.StatementError) as blocked:
            connection.exec_driver_sql("SELECT 1")
        assert isinstance(blocked.value.orig, apply._Stop)
        assert blocked.value.orig.args == ("APPLY_OUTCOME_UNKNOWN",)
        assert physical_connections == [1]
        assert state.attempts == 2
        assert state.lost
    finally:
        connection.close()
        engine.dispose()
