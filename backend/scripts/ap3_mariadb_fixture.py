"""One-time synthetic MariaDB smoke test; no real candidates or APPLY route."""

import argparse
import getpass
import json
import re
import sys
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import NullPool

from app.trend_collection.publication_policy import (
    ContentSnapshot,
    PolicyDecision,
    synthetic_fixture_decision,
)
from scripts.ap3_writer_isolation import validate_connection_target
from scripts.ap3_writer_journal import JournalBlocked, SyntheticJournal
from scripts.ap3_writer_observation import expected_test_target, observe_connection
from scripts.ap3_writer_transaction import (
    BATCH,
    DIGEST,
    FIXTURE_TIME,
    SyntheticItem,
    _stage_items,
)

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


def _verify_session(conn: Connection, baseline=(0, 0, 0)) -> None:
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
    if tuple(checks) != (1, 1) or _counts(conn) != baseline:
        raise RuntimeError("FIXTURE_BASELINE_MISMATCH")
    conn.rollback()


def _policy_snapshot(decision: object) -> ContentSnapshot:
    """Only the independent fixed test fixture may cross this boundary."""
    expected = synthetic_fixture_decision()
    if (type(decision) is not PolicyDecision
            or type(decision.snapshot) is not ContentSnapshot):
        raise RuntimeError("FIXTURE_POLICY_REJECTED")
    if json.dumps(asdict(decision), sort_keys=True, allow_nan=False) != json.dumps(
        asdict(expected), sort_keys=True, allow_nan=False,
    ):
        raise RuntimeError("FIXTURE_POLICY_REJECTED")
    if expected.snapshot is None:
        raise RuntimeError("FIXTURE_POLICY_REJECTED")
    return expected.snapshot


def _verify_previous_fixture(conn: Connection) -> None:
    if _counts(conn) != (2, 2, 2) or conn.exec_driver_sql(
        "SELECT COUNT(*) FROM trends WHERE status = 'HIDDEN'"
    ).scalar_one() != 2:
        raise RuntimeError("FIXTURE_BASELINE_MISMATCH")
    rows = conn.execute(text(
        "SELECT external_id, source_key FROM trend_sources WHERE platform = 'ETC'"
    )).all()
    if set(map(tuple, rows)) != {(item.external_id, item.source_key) for item in BATCH}:
        raise RuntimeError("FIXTURE_BASELINE_MISMATCH")


def _stage_policy_snapshot(conn: Connection, snapshot: ContentSnapshot) -> None:
    _verify_previous_fixture(conn)
    item = SyntheticItem(
        snapshot.external_id, snapshot.title, snapshot.normalized_title,
        snapshot.source_url, snapshot.source_key,
    )
    _stage_items(conn, (item,), summary=snapshot.summary,
                 is_primary=snapshot.is_primary)


def run_fixture(url: URL, journal: MariaDBFixtureJournal, scenario: str,
                *, decision: object = None) -> str:
    """Fixed target, fixed fixture, no arbitrary data or auto retry."""
    if type(journal) is not MariaDBFixtureJournal or scenario not in {
        "rollback", "commit", "policy",
    }:
        raise RuntimeError("FIXTURE_CONFIG_INVALID")
    snapshot = _policy_snapshot(decision) if scenario == "policy" else None
    if snapshot is None and decision is not None:
        raise RuntimeError("FIXTURE_POLICY_REJECTED")
    baseline = (2, 2, 2) if snapshot else (0, 0, 0)
    expected_counts = (3, 3, 3) if snapshot else (2, 2, 2)
    validated = validate_connection_target(url, TARGET)
    batch_id = f"ap3-mariadb-{scenario}-v1"
    digest = (snapshot.content_digest if snapshot else
              sha256(f"{DIGEST}:{scenario}".encode()).hexdigest())
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
            _verify_session(conn, baseline)
            conn.exec_driver_sql("START TRANSACTION")
            if conn.exec_driver_sql("SELECT @@in_transaction").scalar_one() != 1:
                raise RuntimeError("FIXTURE_TRANSACTION_NOT_ACTIVE")
            try:
                if snapshot:
                    _stage_policy_snapshot(conn, snapshot)
                else:
                    _stage_items(conn, BATCH, after_item=(
                        _inject_second_failure if scenario == "rollback" else None
                    ))
                if scenario == "rollback" or _counts(conn) != expected_counts:
                    raise RuntimeError("FIXTURE_STAGE_MISMATCH")
            except FixtureFault:
                conn.rollback()
                if _counts(conn) == baseline:
                    state, result = "ROLLED_BACK", "EXPECTED_ROLLBACK"
            except Exception:
                conn.rollback()
                # Unexpected failure, even if rollback succeeded, is HOLD.
                if _counts(conn) == baseline:
                    state = "ROLLED_BACK"
            else:
                conn.commit()
                if _counts(conn) == expected_counts and conn.exec_driver_sql(
                    "SELECT COUNT(*) FROM trends WHERE status = 'HIDDEN'"
                ).scalar_one() == expected_counts[0]:
                    state = "COMMITTED"
                    result = ("POLICY_FIXTURE_COMMITTED" if snapshot
                              else "FIXTURE_COMMITTED")
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
    parser.add_argument("action", choices=("init", "rollback", "commit", "policy"))
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
            decision = synthetic_fixture_decision() if args.action == "policy" else None
            result = run_fixture(url, journal, args.action, decision=decision)
    except Exception:
        result = "HOLD"
    print(json.dumps({"status": result, "synthetic_only": True,
                      "publication_authorized": False}))
    return 0 if result in {
        "JOURNAL_INITIALIZED", "EXPECTED_ROLLBACK", "FIXTURE_COMMITTED",
        "POLICY_FIXTURE_COMMITTED",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
