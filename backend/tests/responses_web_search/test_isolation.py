"""These checks can pass in Red while the production module is absent."""

import importlib
import os
import socket
import subprocess

import pytest


def test_parent_conftest_and_external_modules_are_not_loaded(isolated_session):
    assert isolated_session is True


@pytest.mark.parametrize("name", ["openai", "sqlalchemy", "sqlite3", "dotenv",
                                   "app.db", "app.main", "app.external_trends"])
def test_forbidden_import_is_blocked_before_module_execution(name):
    with pytest.raises(AssertionError, match="S0 forbidden import"):
        importlib.import_module(name)


@pytest.mark.parametrize("operation", [
    "dns", "network", "process", "write", "key_env", "env_file",
])
def test_io_guard_is_active_without_performing_io(operation, no_external_io):
    # Declare one deliberate blocked probe; product tests expect zero probes.
    no_external_io.append("blocked")
    with pytest.raises(AssertionError, match="S0 external I/O is forbidden"):
        if operation == "dns":
            socket.getaddrinfo("fixture.example.test", 443)
        elif operation == "network":
            socket.create_connection(("fixture.example.test", 443))
        elif operation == "process":
            subprocess.Popen(["must-not-start"])
        elif operation == "write":
            open("must-not-exist-s0.txt", "w")
        elif operation == "key_env":
            os.getenv("OPENAI_API_KEY")  # Blocked before any environment lookup.
        else:
            open(".env")  # Blocked before any file access.
