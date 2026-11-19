"""Isolated synthetic observations; SQLite exercises only duplicate SELECTs."""

from dataclasses import replace
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

from scripts.ap3_writer_isolation import IsolationError
from scripts.ap3_writer_observation import (
    DATABASE,
    TABLE_PRIVILEGES,
    USERNAME,
    check_direct_grants,
    expected_test_target,
    inspect_duplicate,
    observe_connection,
    observe_target,
)

TARGET = expected_test_target("localhost")
ACCOUNT = f"'{USERNAME}'@'localhost'"
GRANTS = [f"GRANT USAGE ON *.* TO {ACCOUNT}"] + [
    f"GRANT {', '.join(sorted(privileges))} ON `{DATABASE}`.`{table}` TO {ACCOUNT}"
    for table, privileges in TABLE_PRIVILEGES.items()
]


def test_direct_grant_profile():
    check_direct_grants(GRANTS, TARGET)
    with_hash = [GRANTS[0] + " IDENTIFIED BY PASSWORD '*" + "A" * 40 + "'"]
    check_direct_grants(with_hash + GRANTS[1:], TARGET)


@pytest.mark.parametrize("extra", [
    f"GRANT SELECT ON *.* TO {ACCOUNT}",
    f"GRANT SELECT ON `{DATABASE}`.* TO {ACCOUNT}",
    f"GRANT SELECT ON `trend_leader`.`trends` TO {ACCOUNT}",
    f"GRANT SELECT ON `{DATABASE}`.`trends` TO {ACCOUNT} WITH GRANT OPTION",
    f"GRANT `other_role` TO {ACCOUNT}",
    f"GRANT DELETE ON `{DATABASE}`.`trends` TO {ACCOUNT}",
])
def test_broad_or_unknown_grants_are_held(extra):
    with pytest.raises(IsolationError):
        check_direct_grants(GRANTS + [extra], TARGET)


def test_missing_grant_is_held():
    with pytest.raises(IsolationError, match="GRANT_PROFILE_MISMATCH"):
        check_direct_grants(GRANTS[:-1], TARGET)


def test_mismatched_target_rejected_before_engine_construction():
    url = URL.create(
        "mysql+pymysql", username=USERNAME, password="synthetic-only",
        host="127.0.0.1", port=3309, database=DATABASE,
    )
    with patch("scripts.ap3_writer_observation.create_engine") as factory:
        with pytest.raises(IsolationError):
            observe_target(url, TARGET)
        with pytest.raises(IsolationError):
            observe_target(url, replace(TARGET, port=3309))
        factory.assert_not_called()


def test_observed_identity_and_role_checked_before_grants():
    conn = Mock()
    conn.exec_driver_sql.return_value.one.return_value = (
        DATABASE, TARGET.current_user, "unexpected_role", "12.3.2-MariaDB"
    )
    with pytest.raises(IsolationError, match="ACTIVE_ROLE_NOT_ALLOWED"):
        observe_connection(conn, TARGET)
    assert conn.exec_driver_sql.call_count == 2
    assert conn.exec_driver_sql.call_args_list[0].args == (
        "START TRANSACTION READ ONLY",
    )


def test_observation_does_not_authorize_publication():
    conn = Mock()
    conn.exec_driver_sql.return_value.one.return_value = (
        DATABASE, TARGET.current_user, None, "12.3.2-MariaDB"
    )
    conn.exec_driver_sql.return_value.scalars.return_value.all.return_value = GRANTS
    result = observe_connection(conn, TARGET)
    assert result["status"] == "DIRECT_GRANTS_MATCH_REVIEW_ONLY"
    assert result["effective_privileges_verified"] is False
    assert result["publication_authorized"] is False
    assert result["database_write_performed"] is False


def test_duplicate_selects_cover_hidden_collision_and_new_identity():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE trends (trend_id INTEGER, "
                          "normalized_title TEXT UNIQUE, status TEXT)"))
        conn.execute(text("CREATE TABLE trend_sources (platform TEXT, "
                          "external_id TEXT, trend_id INTEGER)"))
        conn.execute(text("INSERT INTO trends VALUES (1, 'old title', 'HIDDEN')"))
        old = "github-release:godotengine/godot-builds:123"
        new = "github-release:godotengine/godot-builds:124"
        conn.execute(text("INSERT INTO trend_sources VALUES ('ETC', :id, 1)"),
                     {"id": old})
        assert inspect_duplicate(
            conn, external_id=old, normalized_title="changed title"
        ) == "SKIP_EXISTING_RELEASE"
        assert inspect_duplicate(
            conn, external_id=new, normalized_title="old title"
        ) == "HOLD_TITLE_COLLISION"
        assert inspect_duplicate(
            conn, external_id=new, normalized_title="new title"
        ) == "NEW_UNVERIFIED"
        conn.execute(text("INSERT INTO trend_sources VALUES ('ETC', :id, 1)"),
                     {"id": old})
        assert inspect_duplicate(
            conn, external_id=old, normalized_title="old title"
        ) == "HOLD_IDENTITY_CONFLICT"
        assert conn.execute(text("SELECT status FROM trends")).scalar_one() == "HIDDEN"
    engine.dispose()
