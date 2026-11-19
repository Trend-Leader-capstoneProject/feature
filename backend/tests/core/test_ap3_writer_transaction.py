"""Actual SQLite fixture SQL and persistent journal tests; not MariaDB proof."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import URL

from app.trend_collection.publication_policy import synthetic_fixture_decision
from scripts.ap3_mariadb_fixture import _stage_policy_snapshot
from scripts.ap3_writer_journal import JournalBlocked, SyntheticJournal
from scripts.ap3_writer_transaction import (
    BATCH,
    BATCH_ID,
    DIGEST,
    run_synthetic_batch,
)


@pytest.fixture
def journal(tmp_path):
    path = tmp_path / "fixture-journal.sqlite3"
    result = SyntheticJournal(path, uuid4().hex)
    result.initialize_for_synthetic_test()
    return result, path


@pytest.fixture
def engine():
    db = create_engine("sqlite://")

    @event.listens_for(db, "connect")
    def _foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    with db.begin() as conn:
        for sql in (
            "CREATE TABLE categories (category_id INTEGER PRIMARY KEY, "
            "category_code TEXT, category_name TEXT NOT NULL, "
            "parent_id INTEGER REFERENCES categories(category_id), "
            "is_active INTEGER NOT NULL)",
            "CREATE TABLE trends (trend_id INTEGER PRIMARY KEY, title TEXT NOT NULL, "
            "normalized_title TEXT UNIQUE NOT NULL, summary TEXT, thumbnail_url TEXT, "
            "status TEXT NOT NULL, first_collected_at DATETIME NOT NULL, "
            "last_collected_at DATETIME NOT NULL)",
            "CREATE TABLE trend_sources (source_id INTEGER PRIMARY KEY, "
            "trend_id INTEGER NOT NULL REFERENCES trends(trend_id), "
            "source_key TEXT NOT NULL, source_url TEXT NOT NULL, source_title TEXT, "
            "platform TEXT NOT NULL, collected_at DATETIME NOT NULL, external_id TEXT, "
            "UNIQUE(trend_id, source_key))",
            "CREATE TABLE trend_category_map (trend_category_id INTEGER PRIMARY KEY, "
            "trend_id INTEGER NOT NULL REFERENCES trends(trend_id), "
            "category_id INTEGER NOT NULL REFERENCES categories(category_id), "
            "is_primary INTEGER NOT NULL, created_at DATETIME NOT NULL, "
            "UNIQUE(trend_id, category_id))",
            "INSERT INTO categories VALUES (1, 'IT_DIGITAL', 'IT/디지털', NULL, 1)",
            "INSERT INTO categories VALUES (2, NULL, '소프트웨어·앱', 1, 1)",
        ):
            conn.exec_driver_sql(sql)
    try:
        yield db
    finally:
        db.dispose()


def counts(engine):
    with engine.connect() as conn:
        return tuple(conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
                     for table in ("trends", "trend_sources", "trend_category_map"))


def state(path):
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute("SELECT state FROM attempts").fetchall()


def test_commit_and_repeat_no_write(engine, journal):
    log, path = journal

    @event.listens_for(engine, "before_cursor_execute")
    def _assert_started(_conn, _cursor, statement, _params, _context, _many):
        if statement.startswith("INSERT INTO trend"):
            assert state(path) == [("STARTED",)]

    assert run_synthetic_batch(engine, log) == "COMMITTED"
    assert counts(engine) == (2, 2, 2)
    assert state(path) == [("COMMITTED",)]
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT DISTINCT status FROM trends").all() == [
            ("HIDDEN",)
        ]
        assert conn.exec_driver_sql(
            "SELECT category_id, is_primary FROM trend_category_map"
        ).all() == [(2, 0), (2, 0)]
    with pytest.raises(JournalBlocked, match="JOURNAL_BATCH_ALREADY_ATTEMPTED"):
        run_synthetic_batch(engine, log)
    assert counts(engine) == (2, 2, 2)


def test_second_item_failure_rolls_back_all(engine, journal):
    log, path = journal
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TRIGGER fail_second BEFORE INSERT ON trend_category_map "
            "WHEN NEW.trend_id = 2 BEGIN SELECT RAISE(ABORT, 'fixture fault'); END"
        )
    assert run_synthetic_batch(engine, log) == "ROLLED_BACK"
    assert counts(engine) == (0, 0, 0)
    assert state(path) == [("ROLLED_BACK",)]
    with pytest.raises(JournalBlocked, match="JOURNAL_BATCH_ALREADY_ATTEMPTED"):
        run_synthetic_batch(engine, log)


@pytest.mark.parametrize("sql", [
    "UPDATE categories SET is_active=0 WHERE category_id=1",
    "UPDATE categories SET is_active=0 WHERE category_id=2",
    "INSERT INTO categories VALUES (3, NULL, '소프트웨어·앱', 1, 1)",
])
def test_category_invalid_rolls_back(engine, journal, sql):
    log, path = journal
    with engine.begin() as conn:
        conn.exec_driver_sql(sql)
    assert run_synthetic_batch(engine, log) == "ROLLED_BACK"
    assert counts(engine) == (0, 0, 0)
    assert state(path) == [("ROLLED_BACK",)]


def test_hidden_duplicate_is_held_without_update(engine, journal):
    log, _ = journal
    item = BATCH[0]
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO trends VALUES (1, :title, :normalized, NULL, NULL, "
            "'HIDDEN', '1999-01-01', '1999-01-01')"
        ), {"title": item.title, "normalized": item.normalized_title})
    assert run_synthetic_batch(engine, log) == "ROLLED_BACK"
    assert counts(engine) == (1, 0, 0)
    with engine.connect() as conn:
        assert conn.exec_driver_sql(
            "SELECT status, last_collected_at FROM trends"
        ).one() == ("HIDDEN", "1999-01-01")


def test_unresolved_claim_blocks_even_other_batch(engine, journal):
    log, path = journal
    log.claim(BATCH_ID, DIGEST, uuid4().hex)
    with pytest.raises(JournalBlocked, match="JOURNAL_UNRESOLVED_ATTEMPT"):
        run_synthetic_batch(engine, log)
    with pytest.raises(JournalBlocked, match="JOURNAL_UNRESOLVED_ATTEMPT"):
        log.claim("another-batch", DIGEST, uuid4().hex)
    assert counts(engine) == (0, 0, 0)
    assert state(path) == [("STARTED",)]


def test_unknown_commit_response_not_retried(engine, journal, monkeypatch):
    log, path = journal
    real_commit = engine.dialect.do_commit

    def _commit_then_lose_response(connection):
        real_commit(connection)
        raise RuntimeError("fixture response lost after DBAPI commit")

    monkeypatch.setattr(engine.dialect, "do_commit", _commit_then_lose_response)
    assert run_synthetic_batch(engine, log) == "COMMIT_UNKNOWN"
    assert state(path) == [("COMMIT_UNKNOWN",)]
    assert counts(engine) == (2, 2, 2)
    with pytest.raises(JournalBlocked, match="JOURNAL_UNRESOLVED_ATTEMPT"):
        log.claim("another-batch", DIGEST, uuid4().hex)


def test_finalization_error_never_reports_success(engine, journal, monkeypatch):
    log, path = journal

    def _fail(*_args):
        raise JournalBlocked("FIXTURE_FINALIZATION_FAILURE")

    monkeypatch.setattr(log, "finish", _fail)
    assert run_synthetic_batch(engine, log) == "HOLD_JOURNAL_FINALIZATION"
    assert counts(engine) == (2, 2, 2)
    assert state(path) == [("STARTED",)]
    with pytest.raises(JournalBlocked, match="JOURNAL_UNRESOLVED_ATTEMPT"):
        run_synthetic_batch(engine, log)


def test_missing_corrupt_and_wrong_identity_hold_without_connect(engine, tmp_path):
    path = tmp_path / "missing.sqlite3"
    log = SyntheticJournal(path, uuid4().hex)
    with pytest.raises(JournalBlocked):
        run_synthetic_batch(engine, log)
    assert not path.exists()
    path.write_bytes(b"not sqlite")
    with pytest.raises(JournalBlocked):
        run_synthetic_batch(engine, log)
    assert path.read_bytes() == b"not sqlite"
    assert counts(engine) == (0, 0, 0)


def test_journal_identity_and_provisioning_do_not_replace(engine, journal):
    log, path = journal
    with pytest.raises(JournalBlocked, match="JOURNAL_INITIALIZATION_FAILED"):
        log.initialize_for_synthetic_test()
    wrong = SyntheticJournal(path, uuid4().hex)
    with pytest.raises(JournalBlocked, match="JOURNAL_INTEGRITY_OR_IDENTITY_MISMATCH"):
        run_synthetic_batch(engine, wrong)
    assert counts(engine) == (0, 0, 0)


def test_file_database_rejected_before_journal(tmp_path, journal):
    log, path = journal
    db_path = tmp_path / "not-allowed.sqlite3"
    db = create_engine(f"sqlite:///{db_path}")
    try:
        assert run_synthetic_batch(db, log) == "BLOCKED_NON_SYNTHETIC_TARGET"
        assert not db_path.exists()
        assert state(path) == []
    finally:
        db.dispose()


def test_competing_claims_and_restart_fail_closed(tmp_path):
    path = tmp_path / "concurrent.sqlite3"
    journal_id = uuid4().hex
    SyntheticJournal(path, journal_id).initialize_for_synthetic_test()
    barrier = Barrier(2)

    def claim(index):
        log = SyntheticJournal(path, journal_id)
        barrier.wait(timeout=5)
        try:
            log.claim(f"batch-{index}", DIGEST, uuid4().hex)
        except JournalBlocked:
            return "BLOCKED"
        return "STARTED"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, (1, 2)))
    assert sorted(results) == ["BLOCKED", "STARTED"]
    assert state(path) == [("STARTED",)]
    with pytest.raises(JournalBlocked, match="JOURNAL_UNRESOLVED_ATTEMPT"):
        SyntheticJournal(path, journal_id).claim(
            "after-restart", DIGEST, uuid4().hex,
        )


def test_operational_target_is_rejected_before_connect_or_claim(journal):
    log, path = journal
    engine = Mock()
    engine.url = URL.create("mysql+pymysql", host="127.0.0.1", port=3309,
                            database="trend_leader")
    assert run_synthetic_batch(engine, log) == "BLOCKED_NON_SYNTHETIC_TARGET"
    engine.connect.assert_not_called()
    assert state(path) == []


def test_single_policy_snapshot_uses_existing_stage_sql(engine, journal):
    log, _ = journal
    assert run_synthetic_batch(engine, log) == "COMMITTED"
    snapshot = synthetic_fixture_decision().snapshot
    with engine.begin() as conn:
        _stage_policy_snapshot(conn, snapshot)
    assert counts(engine) == (3, 3, 3)
    with engine.connect() as conn:
        rows = conn.exec_driver_sql(
            "SELECT title, summary, status, is_primary, external_id, source_key "
            "FROM trends JOIN trend_sources USING (trend_id) "
            "JOIN trend_category_map USING (trend_id) ORDER BY trend_id"
        ).all()
    assert rows[:2] == [
        (item.title, None, "HIDDEN", 0, item.external_id, item.source_key)
        for item in BATCH
    ]
    assert rows[2] == (snapshot.title, snapshot.summary, "HIDDEN", 1,
                       snapshot.external_id, snapshot.source_key)


def test_policy_snapshot_does_not_accept_missing_prior_fixture(engine):
    with engine.begin() as conn:
        with pytest.raises(RuntimeError, match="FIXTURE_BASELINE_MISMATCH"):
            _stage_policy_snapshot(conn, synthetic_fixture_decision().snapshot)
    assert counts(engine) == (0, 0, 0)
