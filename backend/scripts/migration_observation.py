"""Offline-callable B-2 DB observation; no CLI or Evidence completion here.

Call only after the future Guard's environment/secret and Evidence-path audit.
No empty candidate, known revision or successful read grants apply approval.
"""

from dataclasses import dataclass, replace
from logging import Logger
from pathlib import Path
from typing import Any

from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from app.core.migration_db_config import MigrationDbSettings
from scripts.migration_preflight import SchemaState, classify_schema_state

START_READ_ONLY = "START TRANSACTION READ ONLY"
TARGET_SQL = "SELECT DATABASE(), CURRENT_USER(), VERSION()"
DEFAULTS_SQL = (
    "SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME "
    "FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = DATABASE()"
)
OBJECTS_SQL = (
    "SELECT CASE WHEN TABLE_TYPE = 'BASE TABLE' THEN 'TABLE' ELSE 'VIEW' END, "
    "TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() "
    "UNION ALL SELECT 'ROUTINE', ROUTINE_NAME FROM information_schema.ROUTINES "
    "WHERE ROUTINE_SCHEMA = DATABASE() "
    "UNION ALL SELECT 'EVENT', EVENT_NAME FROM information_schema.EVENTS "
    "WHERE EVENT_SCHEMA = DATABASE() "
    "UNION ALL SELECT 'TRIGGER', TRIGGER_NAME FROM information_schema.TRIGGERS "
    "WHERE TRIGGER_SCHEMA = DATABASE()"
)
REVISIONS_SQL = "SELECT version_num FROM alembic_version"
ALLOWED_SQL = (START_READ_ONLY, TARGET_SQL, DEFAULTS_SQL, OBJECTS_SQL, REVISIONS_SQL)


class _ObservationPool(NullPool):
    """One-use pool reporting even SQLAlchemy's normally swallowed close errors.

    SQLAlchemy 2.0's private close hook is deliberately version-scoped and
    covered offline. Pool invalidation/close logs may contain raw DBAPI errors;
    use an isolated disabled logger, never alter the application's loggers.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.cleanup_failed = False
        self.logger = Logger("migration_observation.pool")
        self.logger.disabled = True

    def _close_connection(self, connection: Any, *, terminate: bool = False) -> None:
        try:
            if terminate:
                self._dialect.do_terminate(connection)
            else:
                self._dialect.do_close(connection)
        except Exception:
            self.cleanup_failed = True


@dataclass(frozen=True)
class ObservedTarget:
    database: str | None = None
    current_user: str | None = None
    server_version: str | None = None
    database_charset: str | None = None
    database_collation: str | None = None


@dataclass(frozen=True)
class DatabaseObservation:
    """Internal read result, not an OBSERVED inspection or persisted Evidence."""

    observed_target: ObservedTarget = ObservedTarget()
    current_revisions: tuple[str | None, ...] = ()
    version_table_visible: bool | None = None
    business_objects_visible: bool | None = None
    schema_state: SchemaState | None = None
    reason_codes: tuple[str, ...] = ()


def repository_revisions() -> frozenset[str]:
    """Read this checkout's lineage without running env.py or migrations."""
    directory = Path(__file__).resolve().parents[1] / "alembic"
    script = ScriptDirectory(str(directory))
    if len(script.get_heads()) != 1:
        raise ValueError("Repository lineage is ambiguous")
    revisions = frozenset(revision.revision for revision in script.walk_revisions())
    if not revisions:
        raise ValueError("Repository lineage is unavailable")
    return revisions


def _rows(connection: Any, sql: str) -> list[Any]:
    if sql not in ALLOWED_SQL:
        raise ValueError("SQL is not allowed")
    result = connection.exec_driver_sql(sql)
    try:
        return [] if sql == START_READ_ONLY else result.fetchall()
    finally:
        result.close()


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _read(
    connection: Any, settings: MigrationDbSettings, known_revisions: frozenset[str]
) -> DatabaseObservation:
    targets = _rows(connection, TARGET_SQL)
    if len(targets) != 1 or len(targets[0]) != 3:
        raise ValueError("Target metadata unavailable")
    database, current_user, version = targets[0]
    if not all(_nonempty(value) for value in targets[0]):
        raise ValueError("Target metadata unavailable")
    user, separator, host = current_user.rpartition("@")
    if not user or not separator or not host or "mariadb" not in version.lower():
        raise ValueError("Target metadata invalid")
    target = ObservedTarget(database, current_user, version)
    if database != settings.name or user != settings.user:
        return DatabaseObservation(
            observed_target=target, reason_codes=("TARGET_MISMATCH",)
        )
    defaults = _rows(connection, DEFAULTS_SQL)
    if (
        len(defaults) != 1
        or len(defaults[0]) != 2
        or not all(_nonempty(value) for value in defaults[0])
    ):
        raise ValueError("Database defaults unavailable")
    target = replace(
        target, database_charset=defaults[0][0], database_collation=defaults[0][1]
    )
    objects = _rows(connection, OBJECTS_SQL)
    if any(len(row) != 2 or not all(_nonempty(v) for v in row) for row in objects):
        raise ValueError("Object metadata unavailable")
    # A view named alembic_version must not be queried as a version table.
    visible = any(
        kind == "TABLE" and name == "alembic_version" for kind, name in objects
    )
    business = any(
        kind != "TABLE" or name != "alembic_version" for kind, name in objects
    )
    revisions = (
        tuple(row[0] for row in _rows(connection, REVISIONS_SQL)) if visible else ()
    )
    if any(value is not None and not isinstance(value, str) for value in revisions):
        raise ValueError("Revision metadata invalid")
    # Preserve NULL observations. Supply no valid heads to the pure classifier
    # when a NULL is present: a visible version table then stays indeterminate.
    classification_revisions = (
        tuple(value for value in revisions if isinstance(value, str))
        if all(isinstance(value, str) for value in revisions)
        else ()
    )
    state = classify_schema_state(
        version_table_visible=visible,
        current_revisions=classification_revisions,
        business_objects_visible=business,
        known_revisions=known_revisions,
    )
    return DatabaseObservation(
        observed_target=target,
        current_revisions=revisions,
        version_table_visible=visible,
        business_objects_visible=business,
        schema_state=state,
        reason_codes=("SCHEMA_INDETERMINATE",) if state == "INDETERMINATE" else (),
    )


def observe_database(settings: MigrationDbSettings) -> DatabaseObservation:
    """Own a fresh engine/connection, fail closed, never retry or reconnect.

    First *application* SQL is READ ONLY. Dialect/DBAPI initialization precedes
    it. SQLAlchemy's logical autobegin does not emit BEGIN on this dialect.
    Real MariaDB transaction enforcement remains an isolated integration gate.
    P0-B environment and P0-A path audits belong to the future Guard, not here.
    """
    try:
        settings = MigrationDbSettings.model_validate(settings.model_dump())
        url = settings.connection_url
    except Exception:
        return DatabaseObservation(reason_codes=("SETTINGS_INVALID",))
    try:
        known_revisions = repository_revisions()
    except Exception:
        return DatabaseObservation(reason_codes=("OBSERVATION_FAILED",))

    engine = connection = None
    result = DatabaseObservation()
    reason = "DB_CONNECTION_FAILED"
    try:
        engine = create_engine(
            url,
            poolclass=_ObservationPool,
            pool_pre_ping=False,
            pool_reset_on_return=None,
            echo=False,
            hide_parameters=True,
            connect_args={
                "connect_timeout": settings.connection_timeout,
                "charset": "utf8mb4",
                "autocommit": False,
            },
        )
        connection = engine.connect()
        reason = "READ_ONLY_NOT_ESTABLISHED"
        _rows(connection, START_READ_ONLY)
        reason = "OBSERVATION_FAILED"
        result = _read(connection, settings, known_revisions)
    except Exception:
        # Do not return, log or chain the driver exception or URL.
        result = DatabaseObservation(reason_codes=(reason,))
    finally:
        cleanup_failed = False
        if connection is not None:
            for cleanup in (connection.rollback, connection.close):
                try:
                    cleanup()
                except Exception:
                    cleanup_failed = True
        if engine is not None:
            observation_pool = engine.pool
            try:
                engine.dispose()
            except Exception:
                cleanup_failed = True
            cleanup_failed = cleanup_failed or observation_pool.cleanup_failed
        if cleanup_failed:
            reasons = tuple(dict.fromkeys((*result.reason_codes, "OBSERVATION_FAILED")))
            result = DatabaseObservation(reason_codes=reasons)
    return result
