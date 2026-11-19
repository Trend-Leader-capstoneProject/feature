"""MariaDB fixture boundary tests; real MariaDB remains a local verification."""

from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError

from scripts.ap3_mariadb_fixture import (
    TARGET,
    FixtureFault,
    MariaDBFixtureJournal,
    _inject_second_failure,
    run_fixture,
)
from scripts.ap3_writer_isolation import IsolationError
from scripts.ap3_writer_journal import JournalBlocked, SyntheticJournal
from scripts.ap3_writer_transaction import BATCH, _stage_items


def url(port=3307):
    return URL.create("mysql+pymysql", username=TARGET.username,
                      password="synthetic", host=TARGET.host,
                      port=port, database=TARGET.database)


@pytest.fixture
def journal(tmp_path):
    result = MariaDBFixtureJournal(tmp_path / "journal.sqlite3", uuid4().hex)
    result.initialize_for_synthetic_test()
    return result


def test_wrong_target_rejected_before_engine(journal):
    with patch("scripts.ap3_mariadb_fixture.create_engine") as factory:
        with pytest.raises(IsolationError):
            run_fixture(url(3309), journal, "commit")
        factory.assert_not_called()


def test_missing_journal_rejected_before_engine(tmp_path):
    missing = MariaDBFixtureJournal(tmp_path / "missing.sqlite3", uuid4().hex)
    with patch("scripts.ap3_mariadb_fixture.create_engine") as factory:
        with pytest.raises(JournalBlocked):
            run_fixture(url(), missing, "commit")
        factory.assert_not_called()


def test_sqlite_journal_identity_not_reused(tmp_path):
    path = tmp_path / "journal.sqlite3"
    identity = uuid4().hex
    SyntheticJournal(path, identity).initialize_for_synthetic_test()
    with pytest.raises(JournalBlocked):
        MariaDBFixtureJournal(path, identity).claim("batch", "a" * 64, uuid4().hex)


def test_expected_fault_only_for_second_duplicate():
    conn = Mock()
    _inject_second_failure(conn, 0, 1, 2)
    conn.execute.assert_not_called()
    conn.execute.side_effect = IntegrityError("sql", {}, Exception(1062))
    with pytest.raises(FixtureFault):
        _inject_second_failure(conn, 1, 2, 2)
    conn.execute.side_effect = IntegrityError("sql", {}, Exception(1452))
    with pytest.raises(IntegrityError):
        _inject_second_failure(conn, 1, 2, 2)


@pytest.mark.parametrize("scenario,stage_failure,counts,expected", [
    ("rollback", FixtureFault, [(0, 0, 0)], "EXPECTED_ROLLBACK"),
    ("rollback", RuntimeError, [(0, 0, 0)], "HOLD"),
    ("commit", None, [(2, 2, 2), (2, 2, 2)], "FIXTURE_COMMITTED"),
])
def test_transaction_paths(journal, scenario, stage_failure, counts, expected):
    with (
        patch("scripts.ap3_mariadb_fixture.create_engine") as factory,
        patch("scripts.ap3_mariadb_fixture._verify_session"),
        patch("scripts.ap3_mariadb_fixture._stage_items") as stage,
        patch("scripts.ap3_mariadb_fixture._counts", side_effect=counts),
    ):
        conn = factory.return_value.connect.return_value.__enter__.return_value
        conn.exec_driver_sql.return_value.scalar_one.side_effect = [1, 2]
        stage.side_effect = stage_failure
        assert run_fixture(url(), journal, scenario) == expected
        if scenario == "rollback":
            conn.rollback.assert_called_once()
            conn.commit.assert_not_called()
        else:
            conn.commit.assert_called_once()
        with pytest.raises(JournalBlocked):
            run_fixture(url(), journal, scenario)


def test_session_rejection_never_stages(journal):
    with (
        patch("scripts.ap3_mariadb_fixture.create_engine"),
        patch("scripts.ap3_mariadb_fixture._verify_session",
              side_effect=IsolationError),
        patch("scripts.ap3_mariadb_fixture._stage_items") as stage,
    ):
        assert run_fixture(url(), journal, "commit") == "HOLD"
        stage.assert_not_called()
        with pytest.raises(JournalBlocked, match="UNRESOLVED"):
            run_fixture(url(), journal, "rollback")


def test_stage_invokes_fault_hook_after_each_map():
    conn = Mock()
    conn.execute.return_value.first.return_value = None
    conn.execute.return_value.lastrowid = 1
    hook = Mock()
    with patch("scripts.ap3_writer_transaction._category_id", return_value=2):
        _stage_items(conn, BATCH, after_item=hook)
    assert [call.args[1] for call in hook.call_args_list] == [0, 1]
    assert conn.execute.call_count == 10
