"""One-time synthetic MariaDB smoke test; no real candidates or APPLY route."""

import argparse
import getpass
import json
import re
import sys
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, URL
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import NullPool

from scripts.ap3_writer_isolation import validate_connection_target
from scripts.ap3_writer_journal import JournalBlocked, SyntheticJournal
from scripts.ap3_writer_observation import expected_test_target, observe_connection
from scripts.ap3_writer_transaction import BATCH, DIGEST, FIXTURE_TIME, _stage_items

TARGET = expected_test_target("172.20.0.1")
TABLES = ("trends", "trend_sources", "trend_category_map")


class MariaDBFixtureJournal(SyntheticJournal):
    profile_id = "AP3_SYNTHETIC_MARIADB"
    target = "127.0.0.1:3307/trend_leader_writer_test/trend_writer_test@172.20.0.1"

    def __init__(self, path: Path, journal_id: str) -> None:
        # Domain separation prevents reusing a SQLite fixture journal identity.
        if not re.fullmatch(r"[a-f0-9]{32}", journal_id):
            raise JournalBlocked("JOURNAL_CONFIG_INVALID")
        identity = sha256(f"{self.target}:{journal_id}".encode()).hexdigest()[:32]
        super().__init__(path, identity)


class FixtureFault(RuntimeError):
    """Expected, injected duplicate map error only."""


def _inject_second_failure(conn: Connection, index: int, trend_id: int,
                           category_id: int) -> None:
    if index != 1:
        return
    try:
        conn.execute(text(
            "INSERT INTO trend_category_map (trend_id, category_id, is_primary, "
            "created_at) VALUES (:id, :category, 0, :at)"
        ), {"id": trend_id, "category": category_id, "at": FIXTURE_TIME})
    except IntegrityError as exc:
        if getattr(exc.orig, "args", ())[:1] == (1062,):
            raise FixtureFault("EXPECTED_DUPLICATE_MAP") from None
        raise
    raise RuntimeError("EXPECTED_DUPLICATE_MAP_NOT_REJECTED")


def _counts(conn: Connection) -> tuple[int, ...]:
    return tuple(conn.exec_driver_sql(f"SELECT COUNT(*) FROM {table}").scalar_one()
                 for table in TABLES)


def _verify_session(conn: Connection) -> None:
    observe_connection(conn, TARGET)
    engines = conn.execute(text(
        "SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN "
        "('categories','trends','trend_sources','trend_category_map')"
    )).all()
    if dict(engines) != {name: "InnoDB" for name in (*TABLES, "categories")}:
        raise RuntimeError("FIXTURE_ENGINE_MISMATCH")
    checks = conn.exec_driver_sql(
        "SELECT @@session.foreign_key_checks, @@session.unique_checks"
    ).one()
    if tuple(checks) != (1, 1) or _counts(conn) != (0, 0, 0):
        raise RuntimeError("FIXTURE_BASELINE_MISMATCH")
    conn.rollback()


def run_fixture(url: URL, journal: MariaDBFixtureJournal, scenario: str) -> str:
    """Fixed target, fixed fixture, no arbitrary data or auto retry."""
    if type(journal) is not MariaDBFixtureJournal or scenario not in {
        "rollback", "commit",
    }:
        raise RuntimeError("FIXTURE_CONFIG_INVALID")
    validated = validate_connection_target(url, TARGET)
    batch_id = f"ap3-mariadb-{scenario}-v1"
    digest = sha256(f"{DIGEST}:{scenario}".encode()).hexdigest()
    attempt = uuid4().hex
    journal.claim(batch_id, digest, attempt)
    state = "COMMIT_UNKNOWN"
    result = "HOLD"
    engine = None
    try:
        engine = create_engine(
            validated, poolclass=NullPool, hide_parameters=True,
            connect_args={"connect_timeout": 5, "charset": "utf8mb4"},
        )
        with engine.connect() as conn:
            _verify_session(conn)
            conn.exec_driver_sql("START TRANSACTION")
            if conn.exec_driver_sql("SELECT @@in_transaction").scalar_one() != 1:
                raise RuntimeError("FIXTURE_TRANSACTION_NOT_ACTIVE")
            try:
                _stage_items(conn, BATCH, after_item=(
                    _inject_second_failure if scenario == "rollback" else None
                ))
                if scenario != "commit" or _counts(conn) != (2, 2, 2):
                    raise RuntimeError("FIXTURE_STAGE_MISMATCH")
            except FixtureFault:
                conn.rollback()
                if _counts(conn) == (0, 0, 0):
                    state, result = "ROLLED_BACK", "EXPECTED_ROLLBACK"
            except Exception:
                conn.rollback()
                # Unexpected failure, even if rollback succeeded, is HOLD.
                if _counts(conn) == (0, 0, 0):
                    state = "ROLLED_BACK"
            else:
                conn.commit()
                if _counts(conn) == (2, 2, 2) and conn.exec_driver_sql(
                    "SELECT COUNT(*) FROM trends WHERE status = 'HIDDEN'"
                ).scalar_one() == 2:
                    state, result = "COMMITTED", "FIXTURE_COMMITTED"
    except Exception:
        state, result = "COMMIT_UNKNOWN", "HOLD"
    finally:
        if engine is not None:
            engine.dispose()
    try:
        journal.finish(batch_id, digest, attempt, state)
    except JournalBlocked:
        return "HOLD_JOURNAL_FINALIZATION"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("init", "rollback", "commit"))
    parser.add_argument("--journal-id", required=True)
    args = parser.parse_args()
    result = "HOLD"
    try:
        directory = Path.home() / ".trend-leader" / "writer-journal"
        if (not sys.platform.startswith("win") or not directory.is_dir()
                or directory.is_symlink() or directory.is_junction()
                or directory.parent.is_symlink() or directory.parent.is_junction()):
            raise RuntimeError("FIXTURE_JOURNAL_DIRECTORY_INVALID")
        path = directory / "isolated-writer.sqlite3"
        journal = MariaDBFixtureJournal(path, args.journal_id)
        if args.action == "init":
            journal.initialize_for_synthetic_test()
            result = "JOURNAL_INITIALIZED"
        else:
            if not sys.stdin.isatty() or not sys.stderr.isatty():
                raise RuntimeError("INTERACTIVE_TERMINAL_REQUIRED")
            password = getpass.getpass("Isolated test writer password: ")
            url = URL.create(
                "mysql+pymysql", username=TARGET.username, password=password,
                host=TARGET.host, port=TARGET.port, database=TARGET.database,
            )
            result = run_fixture(url, journal, args.action)
    except Exception:
        result = "HOLD"
    print(json.dumps({"status": result, "synthetic_only": True,
                      "publication_authorized": False}))
    return 0 if result in {
        "JOURNAL_INITIALIZED", "EXPECTED_ROLLBACK", "FIXTURE_COMMITTED",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
