"""Read-only isolated DB observation and Source-first duplicate decisions.

No DML, publication authorization, journal or writer entry point exists here.
Only the proposed dedicated 3307 test profile is supported.
"""

import argparse
import getpass
import json
import re
import sys
from collections.abc import Iterable

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Connection
from sqlalchemy.pool import NullPool

from scripts.ap3_writer_isolation import (
    ExpectedTestTarget,
    IsolationError,
    validate_connection_target,
    validate_session_identity,
)

DATABASE = "trend_leader_writer_test"
USERNAME = "trend_writer_test"
TABLE_PRIVILEGES = {
    "categories": frozenset({"SELECT"}),
    "trends": frozenset({"SELECT", "INSERT"}),
    "trend_sources": frozenset({"SELECT", "INSERT"}),
    "trend_category_map": frozenset({"SELECT", "INSERT"}),
}


def expected_test_target(account_host: str) -> ExpectedTestTarget:
    # This is the independently supplied expected MariaDB account host,
    # not the address to connect to and not derived from CURRENT_USER().
    if not re.fullmatch(r"[a-zA-Z0-9_.:%-]{1,255}", account_host):
        raise IsolationError("ACCOUNT_HOST_INVALID")
    return ExpectedTestTarget(
        "127.0.0.1", 3307, DATABASE, USERNAME, f"{USERNAME}@{account_host}"
    )


def check_direct_grants(
    grants: Iterable[str], expected: ExpectedTestTarget,
) -> None:
    """Recognize only the narrow table-grant profile, not every SQL grammar.

    Never log grant statements (USAGE can include an authentication hash).
    Role assignments, broader privileges and unknown syntax are rejected.
    This is not proof of all effective privileges (e.g. PUBLIC grants).
    """
    if expected != expected_test_target(expected.current_user.partition("@")[2]):
        raise IsolationError("OBSERVATION_TARGET_MISMATCH")
    user, _, host = expected.current_user.partition("@")
    # MariaDB can render the same account with backticks or single quotes.
    principal = "(?:" + "|".join(
        re.escape(f"{quote}{user}{quote}@{quote}{host}{quote}")
        for quote in ("'", "`")
    ) + ")"
    usage = re.compile(
        r"GRANT USAGE ON \*\.\* TO " + principal
        + r"(?: IDENTIFIED BY PASSWORD '\*[0-9A-Fa-f]{40}')?"
    )
    table_grant = re.compile(
        r"GRANT ([A-Z, ]+) ON `" + re.escape(DATABASE)
        + r"`\.`([a-z_]+)` TO " + principal
    )
    observed: dict[str, frozenset[str]] = {}
    usage_seen = False
    for grant in grants:
        if not isinstance(grant, str):
            raise IsolationError("GRANT_FORMAT_UNRECOGNIZED")
        if usage.fullmatch(grant):
            if usage_seen:
                raise IsolationError("GRANT_DUPLICATE")
            usage_seen = True
            continue
        match = table_grant.fullmatch(grant)
        if match is None:
            raise IsolationError("GRANT_SCOPE_OR_FORMAT_UNRECOGNIZED")
        privileges = tuple(p.strip() for p in match[1].split(","))
        table = match[2]
        if table in observed or len(privileges) != len(set(privileges)):
            raise IsolationError("GRANT_DUPLICATE")
        observed[table] = frozenset(privileges)
    if not usage_seen or observed != TABLE_PRIVILEGES:
        raise IsolationError("GRANT_PROFILE_MISMATCH")


def observe_connection(connection: Connection, expected: ExpectedTestTarget):
    """Inspect a single session; caller owns rollback and connection lifetime."""
    if expected != expected_test_target(expected.current_user.partition("@")[2]):
        raise IsolationError("OBSERVATION_TARGET_MISMATCH")
    connection.exec_driver_sql("START TRANSACTION READ ONLY")
    database, account, role, version = connection.exec_driver_sql(
        "SELECT DATABASE(), CURRENT_USER(), CURRENT_ROLE(), VERSION()"
    ).one()
    validate_session_identity(
        expected=expected, database=database, current_user=account
    )
    if not isinstance(version, str) or "mariadb" not in version.lower():
        raise IsolationError("MARIADB_NOT_CONFIRMED")
    if role is not None:
        raise IsolationError("ACTIVE_ROLE_NOT_ALLOWED")
    grants = connection.exec_driver_sql("SHOW GRANTS").scalars().all()
    check_direct_grants(grants, expected)
    return {
        "status": "DIRECT_GRANTS_MATCH_REVIEW_ONLY",
        "publication_authorized": False,
        "database_write_performed": False,
        "effective_privileges_verified": False,
    }


def observe_target(url: URL, expected: ExpectedTestTarget):
    if expected != expected_test_target(expected.current_user.partition("@")[2]):
        raise IsolationError("OBSERVATION_TARGET_MISMATCH")
    validated = validate_connection_target(url, expected)
    engine = create_engine(
        validated, poolclass=NullPool, hide_parameters=True,
        connect_args={"connect_timeout": 5},
    )
    try:
        with engine.connect() as connection:
            try:
                return observe_connection(connection, expected)
            finally:
                connection.rollback()
    finally:
        engine.dispose()


def inspect_duplicate(
    connection: Connection, *, external_id: str, normalized_title: str,
) -> str:
    """Read-only classification; not a reservation or a concurrency guarantee.

    Future writer must repeat inside the serialized transaction. A duplicate
    in an already finalized batch follows the frozen batch HOLD rule.
    """
    if (
        not isinstance(external_id, str)
        or not re.fullmatch(
            r"github-release:godotengine/godot-builds:[1-9][0-9]{0,19}",
            external_id,
        )
        or not isinstance(normalized_title, str)
        or not 1 <= len(normalized_title) <= 255
        or normalized_title != normalized_title.strip()
    ):
        raise IsolationError("DUPLICATE_INPUT_INVALID")
    rows = connection.execute(
        text("SELECT external_id FROM trend_sources "
             "WHERE platform = :platform AND external_id = :external_id LIMIT 2"),
        {"platform": "ETC", "external_id": external_id},
    ).scalars().all()
    if len(rows) > 1 or (rows and rows[0] != external_id):
        return "HOLD_IDENTITY_CONFLICT"
    if rows:
        return "SKIP_EXISTING_RELEASE"
    exists = connection.execute(
        text("SELECT trend_id FROM trends "
             "WHERE normalized_title = :title LIMIT 1"),
        {"title": normalized_title},
    ).scalar_one_or_none()
    return "HOLD_TITLE_COLLISION" if exists is not None else "NEW_UNVERIFIED"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-host", required=True)
    args = parser.parse_args()
    try:
        expected = expected_test_target(args.account_host)
        if not sys.stdin.isatty() or not sys.stderr.isatty():
            raise IsolationError("INTERACTIVE_TERMINAL_REQUIRED")
        password = getpass.getpass("Isolated test writer password: ")
        url = URL.create(
            "mysql+pymysql", username=expected.username, password=password,
            host=expected.host, port=expected.port, database=expected.database,
        )
        result = observe_target(url, expected)
    except IsolationError as exc:
        result = {"status": "HOLD", "reason": str(exc)}
    except Exception:
        # DB exceptions may contain connection inputs or raw grant material.
        result = {"status": "HOLD", "reason": "OBSERVATION_FAILED"}
    result.update(publication_authorized=False, database_write_performed=False)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "DIRECT_GRANTS_MATCH_REVIEW_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
