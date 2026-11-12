"""S0 only: run with --confcutdir=tests/responses_web_search.

No application, dotenv, SDK or database import is allowed during collection.
"""

import builtins
import importlib.abc
import io
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

FORBIDDEN_MODULES = (
    "openai", "sqlalchemy", "pymysql", "sqlite3", "dotenv",
    "httpx", "httpx2", "requests", "urllib.request", "http.client",
    "app.main", "app.core", "app.db", "app.api", "app.models",
    "app.repositories", "app.external_trends",
)


def forbidden(name):
    return any(name == item or name.startswith(item + ".")
               for item in FORBIDDEN_MODULES)


class NoExternalImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if forbidden(fullname):
            raise AssertionError(f"S0 forbidden import: {fullname}")
        return None


# Collection guard is installed before test modules are imported.
_import_guard = NoExternalImports()
sys.meta_path.insert(0, _import_guard)


def pytest_sessionfinish(session, exitstatus):
    if _import_guard in sys.meta_path:
        sys.meta_path.remove(_import_guard)


@pytest.fixture(autouse=True)
def no_external_io(monkeypatch):
    """Even swallowed I/O exceptions fail the test at teardown."""
    attempts = []
    expected = []

    def blocked(*args, **kwargs):
        attempts.append("blocked")
        raise AssertionError("S0 external I/O is forbidden")

    for name in ("connect", "connect_ex", "send", "sendall", "sendto"):
        monkeypatch.setattr(socket.socket, name, blocked)
    for name in (
        "create_connection", "getaddrinfo", "gethostbyname",
        "gethostbyname_ex", "gethostbyaddr",
    ):
        monkeypatch.setattr(socket, name, blocked)
    monkeypatch.setattr(subprocess, "Popen", blocked)
    monkeypatch.setattr(os, "system", blocked)
    monkeypatch.setattr(os, "popen", blocked)

    original_open = builtins.open
    original_io_open = io.open
    original_os_open = os.open
    original_env_getitem = type(os.environ).__getitem__

    def private_config_file(file):
        return isinstance(file, (str, bytes, os.PathLike)) and (
            Path(os.fsdecode(file)).name.startswith(".env")
        )

    def guarded_env_getitem(environ, key):
        if str(key).upper().startswith(("OPENAI", "DATABASE", "TEST_DATABASE")):
            return blocked()
        return original_env_getitem(environ, key)

    def guarded_open(file, mode="r", *args, **kwargs):
        if private_config_file(file) or any(flag in mode for flag in "wax+"):
            return blocked()
        return original_open(file, mode, *args, **kwargs)

    def guarded_io_open(file, mode="r", *args, **kwargs):
        if private_config_file(file) or any(flag in mode for flag in "wax+"):
            return blocked()
        return original_io_open(file, mode, *args, **kwargs)

    def guarded_os_open(path, flags, *args, **kwargs):
        if private_config_file(path):
            return blocked()
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            return blocked()
        return original_os_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(io, "open", guarded_io_open)
    monkeypatch.setattr(os, "open", guarded_os_open)
    monkeypatch.setattr(type(os.environ), "__getitem__", guarded_env_getitem)
    yield expected
    assert attempts == expected, "Unexpected or swallowed S0 I/O attempt"


@pytest.fixture
def isolated_session():
    """A passing check here establishes isolation, not product correctness."""
    assert not [name for name in sys.modules if forbidden(name)]
    parent = Path(__file__).resolve().parents[1] / "conftest.py"
    assert not any(
        Path(filename).resolve() == parent
        for module in tuple(sys.modules.values())
        if (filename := getattr(module, "__file__", None))
    )
    return True
