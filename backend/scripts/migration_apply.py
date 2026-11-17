"""Internal Guard APPLY integration; operational CLI remains disabled.

No adapter currently establishes operator approval, image/server identity,
recovery review, dedicated least-privilege account or protected durable storage.
run_apply() therefore cannot read inputs, connect or consume approvals. The
explicit internal request below is for trusted integration/harness callers;
constructing it from submitted JSON/environment does NOT establish trust.
"""

import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from logging import Logger
from pathlib import Path
from typing import Callable

from alembic.config import Config
from sqlalchemy import create_engine, event

from alembic import command
from app.core.migration_db_config import MigrationDbSettings
from scripts.migration_apply_audit import AuditRejected, FileApplyAudit
from scripts.migration_approval import ComparisonContext, compare_approval
from scripts.migration_environment import audit_environment_conflicts
from scripts.migration_observation import _ObservationPool, _read, repository_revisions

# Fixed read-only catalog queries. No user SQL, data rows, grant strings or
# schema names are emitted to stdout/logs/audit. Hashes are review pins only.
SCHEMA_SQL = (
    "SELECT TABLE_NAME, TABLE_TYPE, ENGINE, TABLE_COLLATION "
    "FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() "
    "ORDER BY TABLE_NAME",
    "SELECT TABLE_NAME, COLUMN_NAME, ORDINAL_POSITION, COLUMN_TYPE, IS_NULLABLE, "
    "COLUMN_DEFAULT, EXTRA, CHARACTER_SET_NAME, COLLATION_NAME, "
    "IS_GENERATED, GENERATION_EXPRESSION "
    "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
    "ORDER BY TABLE_NAME, ORDINAL_POSITION",
    "SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME, "
    "SUB_PART, INDEX_TYPE FROM information_schema.STATISTICS "
    "WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX",
    "SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, ORDINAL_POSITION, "
    "REFERENCED_TABLE_SCHEMA, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME "
    "FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA = DATABASE() "
    "ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION",
    "SELECT TABLE_NAME, CONSTRAINT_NAME, UPDATE_RULE, DELETE_RULE "
    "FROM information_schema.REFERENTIAL_CONSTRAINTS "
    "WHERE CONSTRAINT_SCHEMA = DATABASE() ORDER BY TABLE_NAME, CONSTRAINT_NAME",
    "SELECT TABLE_NAME, CONSTRAINT_NAME, CHECK_CLAUSE "
    "FROM information_schema.CHECK_CONSTRAINTS WHERE CONSTRAINT_SCHEMA = DATABASE() "
    "ORDER BY TABLE_NAME, CONSTRAINT_NAME",
    "SELECT TABLE_NAME, VIEW_DEFINITION, CHECK_OPTION, IS_UPDATABLE, DEFINER, "
    "SECURITY_TYPE FROM information_schema.VIEWS WHERE TABLE_SCHEMA = DATABASE() "
    "ORDER BY TABLE_NAME",
    "SELECT TRIGGER_NAME, EVENT_MANIPULATION, EVENT_OBJECT_TABLE, ACTION_ORDER, "
    "ACTION_STATEMENT, ACTION_TIMING, DEFINER FROM information_schema.TRIGGERS "
    "WHERE TRIGGER_SCHEMA = DATABASE() ORDER BY TRIGGER_NAME",
    "SELECT ROUTINE_NAME, ROUTINE_TYPE, DATA_TYPE, ROUTINE_DEFINITION, "
    "SECURITY_TYPE, DEFINER FROM information_schema.ROUTINES "
    "WHERE ROUTINE_SCHEMA = DATABASE() ORDER BY ROUTINE_NAME, ROUTINE_TYPE",
    "SELECT EVENT_NAME, EVENT_DEFINITION, EVENT_TYPE, EXECUTE_AT, INTERVAL_VALUE, "
    "INTERVAL_FIELD, STATUS, ON_COMPLETION, DEFINER FROM information_schema.EVENTS "
    "WHERE EVENT_SCHEMA = DATABASE() ORDER BY EVENT_NAME",
)
GET_LOCK = "SELECT GET_LOCK(%s, %s)"
LOCK_OWNER = "SELECT IS_USED_LOCK(%s)"
RELEASE_LOCK = "SELECT RELEASE_LOCK(%s)"
SESSION_ID = "SELECT CONNECTION_ID()"


@dataclass(frozen=True, repr=False)
class ApplyRequest:
    """Independent reviewed facts, bound to ComparisonContext's Manifest pin.

    Schema hashes cover catalog structure, NOT data integrity or server identity.
    grants_sha256 pins reviewed SHOW GRANTS, NOT a generic privilege validator.
    The caller must independently establish dedicated account, DB identity,
    image actually running, recovery, write pause and protected persistent audit.
    No production adapter exists for these prerequisites. This is not a public
    authorization API or a new operational approval format.
    """

    manifest: bytes
    evidence: bytes
    context: ComparisonContext
    settings: MigrationDbSettings
    audit: FileApplyAudit
    before_schema_sha256: str
    after_schema_sha256: str
    grants_sha256: str
    # Test candidate only; production timeout remains an operational gate.
    lock_timeout: int = 5


class _Stop(Exception):
    pass


@dataclass
class _ConnectionState:
    attempts: int = 0
    lost: bool = False

    def connecting(self, dialect, record, args, kwargs):
        self.attempts += 1
        if self.attempts != 1:
            self.lost = True
            raise _Stop("APPLY_OUTCOME_UNKNOWN")

    def handle_error(self, exception_context):
        if exception_context.is_disconnect:
            self.lost = True


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise _Stop(reason)


def _rows(connection, sql, parameters=()):
    result = connection.exec_driver_sql(sql, parameters)
    try:
        return [tuple(row) for row in result.fetchall()]
    finally:
        result.close()


def _scalar(connection, sql, parameters=()):
    rows = _rows(connection, sql, parameters)
    if len(rows) != 1 or len(rows[0]) != 1:
        raise _Stop("LIVE_CHECK_FAILED")
    return rows[0][0]


def _hash(data) -> str:
    return sha256(json.dumps(data, ensure_ascii=True).encode()).hexdigest()


def schema_fingerprint(connection) -> str:
    """For independent offline review/harness use; never infer approval here."""
    return _hash([_rows(connection, sql) for sql in SCHEMA_SQL])


def grants_fingerprint(connection) -> str:
    # SHOW GRANTS can include credential hashes. Retain only its digest.
    return _hash(sorted(_rows(connection, "SHOW GRANTS")))


def _check_live(connection, settings, manifest, revisions, schema_pin, grants_pin):
    observed = _read(connection, settings, repository_revisions())
    target = observed.observed_target
    _require(
        not observed.reason_codes
        and target.database == manifest["db_name"]
        and target.current_user == manifest["expected_db_account"]
        and target.database_charset == "utf8mb4"
        and target.database_collation == "utf8mb4_unicode_ci"
        and observed.current_revisions == revisions,
        "LIVE_CHECK_FAILED",
    )
    _require(
        schema_fingerprint(connection) == schema_pin
        and grants_fingerprint(connection) == grants_pin,
        "LIVE_CHECK_FAILED",
    )


def _held(connection, name, session):
    _require(
        _scalar(connection, SESSION_ID) == session
        and _scalar(connection, LOCK_OWNER, (name,)) == session,
        "LOCK_NOT_HELD",
    )


def _upgrade(connection, target):
    # No ini/fileConfig: do not enable migration/engine log handlers or a URL.
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
    )
    config.attributes["connection"] = connection
    command.upgrade(config, target)


def run_apply() -> tuple[int, tuple[str, ...]]:
    """Operational adapter intentionally absent: zero I/O, deny before access."""
    return 2, ("MODE_NOT_ENABLED",)


def run_authorized_apply(
    request: ApplyRequest, *, clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> tuple[int, tuple[str, ...]]:
    """Internal one-shot integration. Never retry, reconnect or refund the ID.

    The production CLI cannot obtain an ApplyRequest. Tests supply synthetic
    trusted facts explicitly; a B-3 matches result alone cannot enter here.
    """
    try:
        conflict = audit_environment_conflicts(dict(os.environ))
        if conflict:
            return 2, (conflict,)
        check = compare_approval(
            request.manifest, request.evidence, context=request.context, now=clock(),
        )
        if not check.matches:
            return 2, check.reason_codes
        manifest = json.loads(request.manifest)
        _require(
            all(type(pin) is str and re.fullmatch(r"[0-9a-f]{64}", pin) for pin in (
                request.before_schema_sha256, request.after_schema_sha256,
                request.grants_sha256,
            ))
            and type(request.lock_timeout) is int and 0 <= request.lock_timeout <= 30,
            "LIVE_CHECK_FAILED",
        )
        settings = MigrationDbSettings.model_validate(request.settings.model_dump())
        _require(
            settings.user.casefold() != "root"
            and (settings.host, settings.port, settings.name, settings.user)
            == (manifest["db_host"], manifest["db_port"], manifest["db_name"],
                manifest["expected_db_account"].rpartition("@")[0]),
            "LIVE_CHECK_FAILED",
        )
        url = settings.connection_url
    except Exception:
        return 2, ("APPLY_PREREQUISITES_INVALID",)

    try:
        claim = request.audit.consume(
            manifest["approval_id"], manifest_sha256=request.context.manifest_sha256,
            evidence_sha256=request.context.evidence_sha256,
        )
    except AuditRejected as error:
        reason = error.args[0]
        return (2 if reason == "APPROVAL_ALREADY_USED" else 4), (reason,)
    except Exception:
        return 4, ("AUDIT_WRITE_FAILED",)

    engine = connection = None
    attempted_ddl = lock_acquired = False
    connection_state = _ConnectionState()
    status, reason = "FAILED", "DB_CONNECTION_FAILED"
    # Server-scoped and DB-specific; stable across approvals/projects/host aliases.
    lock_name = "tl-migration:" + sha256(settings.name.encode()).hexdigest()[:48]
    before = manifest["expected_from_revision"]
    before_revisions = () if before is None else (before,)
    session = None
    try:
        engine = create_engine(
            url, poolclass=_ObservationPool, pool_pre_ping=False,
            pool_reset_on_return=None, echo=False, hide_parameters=True,
            connect_args={"connect_timeout": settings.connection_timeout,
                          "charset": "utf8mb4", "autocommit": False},
        )
        engine.logger = Logger("migration_apply.engine")
        engine.logger.disabled = True
        event.listen(engine, "do_connect", connection_state.connecting)
        event.listen(engine, "handle_error", connection_state.handle_error)
        connection = engine.connect()
        reason = "LIVE_CHECK_FAILED"
        session = _scalar(connection, SESSION_ID)
        _require(type(session) is int and session > 0, reason)
        _check_live(connection, settings, manifest, before_revisions,
                    request.before_schema_sha256, request.grants_sha256)
        reason = "LOCK_NOT_ACQUIRED"
        value = _scalar(connection, GET_LOCK, (lock_name, request.lock_timeout))
        _require(type(value) is int and value == 1, reason)
        lock_acquired = True
        # Drop pre-lock read snapshot. GET_LOCK survives COMMIT (L-2 evidence).
        connection.commit()
        _held(connection, lock_name, session)
        reason = "LIVE_CHECK_FAILED"
        _check_live(connection, settings, manifest, before_revisions,
                    request.before_schema_sha256, request.grants_sha256)
        # End autobegin so Alembic owns its per-migration transaction lifecycle.
        connection.commit()
        _held(connection, lock_name, session)
        connection.commit()
        _require(compare_approval(
            request.manifest, request.evidence, context=request.context, now=clock(),
        ).matches, "APPROVAL_TIME_INVALID")
        attempted_ddl = True
        reason = "APPLY_OUTCOME_UNKNOWN"
        _upgrade(connection, manifest["target_revision"])
        connection.commit()
        _held(connection, lock_name, session)
        _check_live(connection, settings, manifest, (manifest["target_revision"],),
                    request.after_schema_sha256, request.grants_sha256)
        status, reason = "APPLIED", "APPLIED"
    except _Stop as error:
        status = "UNKNOWN" if attempted_ddl or connection_state.lost else "FAILED"
        reason = error.args[0]
    except BaseException:
        # Includes operator interruption. DDL cannot be assumed rolled back.
        status = "UNKNOWN" if attempted_ddl or connection_state.lost else "FAILED"
    finally:
        if connection is not None:
            # Never roll back then run SQL on an invalidated Connection: that
            # can trigger SQLAlchemy reconnection. Also blocked by do_connect.
            usable = not connection_state.lost and not connection.invalidated
            if lock_acquired and usable:
                try:
                    _held(connection, lock_name, session)
                    released = _scalar(connection, RELEASE_LOCK, (lock_name,))
                    _require(type(released) is int and released == 1,
                             "LOCK_RELEASE_FAILED")
                    # Another operator may acquire after release; only require
                    # that THIS session no longer owns the cooperative lock.
                    _require(_scalar(connection, LOCK_OWNER, (lock_name,)) != session,
                             "LOCK_RELEASE_FAILED")
                except BaseException:
                    status, reason = "UNKNOWN", "LOCK_RELEASE_FAILED"
            elif lock_acquired:
                status, reason = "UNKNOWN", "LOCK_RELEASE_FAILED"
            try:
                connection.close()
            except BaseException:
                status, reason = "UNKNOWN", "CLEANUP_FAILED"
        if engine is not None:
            apply_pool = engine.pool
            try:
                engine.dispose()
                if apply_pool.cleanup_failed:
                    raise ValueError
            except BaseException:
                status, reason = "UNKNOWN", "CLEANUP_FAILED"
    try:
        request.audit.finish(claim, status, reason)
    except BaseException:
        return 4, ("AUDIT_WRITE_FAILED",)
    return (0 if status == "APPLIED" else 4), (reason,)
