"""Opt-in D2-only lock test. No application, Alembic or shared DB fixtures."""

import os
import socket
from importlib.metadata import version
from logging import Logger
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import URL, create_engine, text
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.integration


class LockTestPool(NullPool):
    """Report DBAPI close failures that SQLAlchemy normally only logs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cleanup_failed = False
        self.logger = Logger("l2_lock_test.pool")
        self.logger.disabled = True

    def _close_connection(self, connection, *, terminate=False):
        try:
            if terminate:
                self._dialect.do_terminate(connection)
            else:
                self._dialect.do_close(connection)
        except Exception:
            self.cleanup_failed = True


def require(condition):
    if not condition:
        raise RuntimeError("L2_LOCK_CHECK_FAILED")


def inputs():
    keys = (
        "HOST",
        "PORT",
        "PASSWORD_FILE",
        "ALLOWED_HOST",
        "ALLOWED_PORT",
        "ALLOWED_CURRENT_USER",
        "ALLOWED_SERVER_HOSTNAME",
        "ALLOWED_SERVER_ID",
        "ALLOWED_DB_IP",
    )
    values = {key: os.environ.get("L2_LOCK_" + key, "") for key in keys}
    require(all(value and value == value.strip() for value in values.values()))
    require(values["HOST"] == "db")
    require(values["PORT"] == "3306")
    addresses = {
        item[4][0] for item in socket.getaddrinfo("db", 3306, type=socket.SOCK_STREAM)
    }
    require(addresses == {values["ALLOWED_DB_IP"]})
    require(values["HOST"] == values["ALLOWED_HOST"])
    require(values["PORT"].isascii() and values["PORT"].isdigit())
    require(1 <= int(values["PORT"]) <= 65535)
    require(values["ALLOWED_CURRENT_USER"].startswith("d2_migrator@"))
    require(bool(values["ALLOWED_CURRENT_USER"].split("@", 1)[1]))
    require(values["PORT"] == values["ALLOWED_PORT"])
    require(int(values["ALLOWED_SERVER_ID"]) >= 0)
    path = Path(values["PASSWORD_FILE"])
    require(path.is_absolute() and path.is_file())
    password = path.read_text(encoding="utf-8").removesuffix("\n").removesuffix("\r")
    require(bool(password) and not any(c in password for c in ("\n", "\r", "\x00")))
    url = URL.create(
        "mysql+pymysql",
        host=values["HOST"],
        port=int(values["PORT"]),
        database="trend_leader_d2_test",
        username="d2_migrator",
        password=password,
        query={"charset": "utf8mb4"},
    )
    return url, values


def scalar(connection, statement, **parameters):
    # Never let SQLAlchemy transparently reconnect an invalidated session.
    require(not connection.closed and not connection.invalidated)
    with connection.execute(text(statement), parameters) as result:
        return result.scalar_one()


def identity(connection, expected):
    require(not connection.closed and not connection.invalidated)
    with connection.execute(
        text(
            "SELECT DATABASE(), CURRENT_USER(), VERSION(), CONNECTION_ID(), "
            "@@hostname, @@server_id"
        )
    ) as result:
        row = result.one()
    require(row[0] == "trend_leader_d2_test")
    require(row[1] == expected["ALLOWED_CURRENT_USER"])
    require("MariaDB" in row[2])
    require(row[4] == expected["ALLOWED_SERVER_HOSTNAME"])
    require(str(row[5]) == expected["ALLOWED_SERVER_ID"])
    return row[3]


def test_same_connection_commit_contention_and_release():
    if os.environ.get("L2_LOCK_RUN") != "D2_LOCK_TEST_APPROVED":
        pytest.skip("D2 lock test requires explicit opt-in")

    engine = None
    connections = []
    failed = False
    # Per-run name, shared by both sessions; never an operational Guard lock.
    name = "tl:d2:l2-test:" + uuid4().hex
    try:
        require(version("SQLAlchemy") == "2.0.57")
        require(version("PyMySQL") == "1.2.4")
        require(version("pytest") == "9.2.0")
        url, expected = inputs()
        engine = create_engine(
            url,
            poolclass=LockTestPool,
            pool_pre_ping=False,
            hide_parameters=True,
            echo=False,
            logging_name="l2_lock_test",
            pool_logging_name="l2_lock_test",
            connect_args={"connect_timeout": 5, "read_timeout": 5, "write_timeout": 5},
        )
        # Isolated loggers: never expose DBAPI exceptions through pool cleanup logs.
        engine.logger.disabled = True
        engine.pool.logger.disabled = True
        owner = engine.connect()
        connections.append(owner)
        contender = engine.connect()
        connections.append(contender)
        owner_id = identity(owner, expected)
        contender_id = identity(contender, expected)
        require(owner_id != contender_id)
        # Both targets must pass before the first lock-changing statement.
        require(scalar(owner, "SELECT GET_LOCK(:name, 0)", name=name) == 1)
        require(scalar(owner, "SELECT IS_USED_LOCK(:name)", name=name) == owner_id)
        owner.commit()
        require(identity(owner, expected) == owner_id)
        require(scalar(owner, "SELECT IS_USED_LOCK(:name)", name=name) == owner_id)
        require(scalar(contender, "SELECT GET_LOCK(:name, 0)", name=name) == 0)
        require(scalar(contender, "SELECT IS_USED_LOCK(:name)", name=name) == owner_id)
        require(scalar(owner, "SELECT RELEASE_LOCK(:name)", name=name) == 1)
        require(scalar(contender, "SELECT IS_USED_LOCK(:name)", name=name) is None)
        # Successful handoff proves the competing session can actually acquire it.
        require(scalar(contender, "SELECT GET_LOCK(:name, 0)", name=name) == 1)
        require(
            scalar(contender, "SELECT IS_USED_LOCK(:name)", name=name) == contender_id
        )
        require(scalar(contender, "SELECT RELEASE_LOCK(:name)", name=name) == 1)
        owner.close()
        require(owner.closed)
        require(scalar(contender, "SELECT IS_USED_LOCK(:name)", name=name) is None)
        contender.close()
        require(contender.closed)
    except Exception:
        # No raw exception/URL/credentials in pytest output, even for connect failure.
        failed = True
    finally:
        # No SQL retry, new connection or KILL. Physically discard any still-open
        # session so an ambiguous acquisition cannot return to a reusable pool.
        for connection in reversed(connections):
            if not connection.closed:
                try:
                    connection.invalidate()
                except Exception:
                    failed = True
                try:
                    connection.close()
                except Exception:
                    failed = True
        if engine is not None:
            try:
                failed = failed or engine.pool.cleanup_failed
                engine.dispose()
                failed = failed or engine.pool.cleanup_failed
            except Exception:
                failed = True
    if failed:
        pytest.fail("L2_LOCK_TEST_FAILED_OR_CLEANUP_UNCERTAIN", pytrace=False)
