"""Synthetic W1-02 comparisons only; no engine, connector, or writes."""

from dataclasses import replace

import pytest
from sqlalchemy.engine import URL

from scripts.ap3_writer_isolation import (
    ExpectedTestTarget,
    IsolationError,
    validate_connection_target,
    validate_session_identity,
)

TARGET = ExpectedTestTarget(
    "127.0.0.1", 3307, "writer_fixture_db", "writer_fixture_user",
    "writer_fixture_user@localhost",
)
URL_FIXTURE = URL.create(
    "mysql+pymysql", username=TARGET.username, password="fixture-only",
    host=TARGET.host, port=TARGET.port, database=TARGET.database,
)


def test_exact_connection_and_session_match():
    assert validate_connection_target(URL_FIXTURE, TARGET) == URL_FIXTURE
    validate_session_identity(
        expected=TARGET, database=TARGET.database, current_user=TARGET.current_user,
    )


@pytest.mark.parametrize("target", [
    None,
    replace(TARGET, host="localhost"),
    replace(TARGET, port=3309),
    replace(TARGET, port=3306),
    replace(TARGET, database="trend_leader"),
    replace(TARGET, database="trend_leader_test"),
    replace(TARGET, username="root", current_user="root@localhost"),
])
def test_untrusted_or_unsafe_expected_target_is_rejected(target):
    with pytest.raises(IsolationError, match="ISOLATION_TARGET_"):
        validate_connection_target(URL_FIXTURE, target)


@pytest.mark.parametrize("url", [
    URL_FIXTURE.set(host="192.0.2.1"),
    URL_FIXTURE.set(port=3308),
    URL_FIXTURE.set(database="other_db"),
    URL_FIXTURE.set(username="other_user"),
    URL_FIXTURE.set(drivername="sqlite"),
    URL_FIXTURE.set(query={"unix_socket": "/tmp/mysql.sock"}),
    URL_FIXTURE.set(password=""),
])
def test_mismatched_or_ambiguous_url_is_rejected(url):
    with pytest.raises(IsolationError, match="ISOLATION_URL_MISMATCH"):
        validate_connection_target(url, TARGET)


@pytest.mark.parametrize("database,current_user", [
    ("other_db", TARGET.current_user),
    (TARGET.database, "writer_fixture_user@%"),
    (TARGET.database, "root@localhost"),
])
def test_observed_session_mismatch_is_rejected(database, current_user):
    with pytest.raises(IsolationError, match="ISOLATION_SESSION_MISMATCH"):
        validate_session_identity(
            expected=TARGET, database=database, current_user=current_user,
        )


def test_malformed_url_reports_only_safe_error_code():
    with pytest.raises(IsolationError) as exc_info:
        validate_connection_target("malformed-fixture-only-secret", TARGET)
    assert str(exc_info.value) == "ISOLATION_URL_INVALID"
