"""Pure AP-3 isolation checks; neither approval nor a DB connection.

The caller must obtain the expected target from a separately trusted test
configuration. Passing these comparisons alone never permits DML or APPLY.
"""

import re
from dataclasses import dataclass

from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


class IsolationError(ValueError):
    """Safe diagnostic without credentials or connection details."""


@dataclass(frozen=True, slots=True)
class ExpectedTestTarget:
    host: str
    port: int
    database: str
    username: str
    current_user: str


def _check_expected(target: ExpectedTestTarget | None) -> ExpectedTestTarget:
    if not isinstance(target, ExpectedTestTarget):
        raise IsolationError("ISOLATION_TARGET_MISSING")
    if (
        target.host != "127.0.0.1"
        or type(target.port) is not int
        or not 1 <= target.port <= 65535
        or target.port in {3306, 3309}
        or not isinstance(target.database, str)
        or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", target.database)
        or target.database in {
            "trend_leader", "trend_leader_test", "mysql", "sys",
            "information_schema", "performance_schema",
        }
        or not isinstance(target.username, str)
        or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", target.username)
        or target.username == "root"
        or not isinstance(target.current_user, str)
        or not target.current_user.startswith(target.username + "@")
        or not target.current_user.partition("@")[2].strip()
    ):
        raise IsolationError("ISOLATION_TARGET_UNSAFE")
    return target


def validate_connection_target(
    url: str | URL, expected: ExpectedTestTarget | None,
) -> URL:
    """Reject ambiguous or non-isolated connection settings before I/O."""
    target = _check_expected(expected)
    try:
        parsed = make_url(url)
        actual = (parsed.host, parsed.port, parsed.database, parsed.username)
    except (ArgumentError, TypeError, ValueError, AttributeError):
        raise IsolationError("ISOLATION_URL_INVALID") from None
    if (
        parsed.drivername != "mysql+pymysql"
        or parsed.query
        or not parsed.password
        or actual != (target.host, target.port, target.database, target.username)
    ):
        raise IsolationError("ISOLATION_URL_MISMATCH")
    return parsed


def validate_session_identity(
    *, expected: ExpectedTestTarget | None, database: str, current_user: str,
) -> None:
    """Compare observed DATABASE()/CURRENT_USER(); grants remain separate."""
    target = _check_expected(expected)
    if (database, current_user) != (target.database, target.current_user):
        raise IsolationError("ISOLATION_SESSION_MISMATCH")
