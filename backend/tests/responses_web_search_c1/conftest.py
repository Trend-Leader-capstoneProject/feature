"""C1 only: use --confcutdir=tests/responses_web_search_c1.

Allow SDK imports and MockTransport; guard external effects, not package reads.
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

FORBIDDEN = (
    "sqlalchemy", "pymysql", "sqlite3", "redis", "dotenv",
    "app.main", "app.core", "app.db", "app.api", "app.models",
    "app.repositories", "app.external_trends",
)


def forbidden(name):
    return any(name == item or name.startswith(item + ".") for item in FORBIDDEN)


class NoOperationalImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if forbidden(fullname):
            raise AssertionError("C1 operational import forbidden")
        return None


_import_guard = NoOperationalImports()
sys.meta_path.insert(0, _import_guard)


def pytest_sessionfinish(session, exitstatus):
    if _import_guard in sys.meta_path:
        sys.meta_path.remove(_import_guard)


@pytest.fixture(autouse=True)
def isolated_io(monkeypatch):
    """Record even swallowed attempts. Only the guard self-test expects attempts."""
    attempts = []
    expected = []

    def blocked(*args, **kwargs):
        attempts.append("blocked")
        raise AssertionError("C1 external effect forbidden")

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
    original_getitem = type(os.environ).__getitem__

    def secret_file(file):
        if not isinstance(file, (str, bytes, os.PathLike)):
            return False
        path = Path(os.fsdecode(file))
        return path.name.startswith(".env") or any(
            part in {".aws", ".ssh"} for part in path.parts
        )

    def guarded_open(file, mode="r", *args, **kwargs):
        if secret_file(file):
            return blocked()
        return original_open(file, mode, *args, **kwargs)

    def guarded_io_open(file, mode="r", *args, **kwargs):
        if secret_file(file):
            return blocked()
        return original_io_open(file, mode, *args, **kwargs)

    def guarded_os_open(file, flags, *args, **kwargs):
        if secret_file(file):
            return blocked()
        return original_os_open(file, flags, *args, **kwargs)

    def guarded_getitem(environ, key):
        name = str(key).upper()
        if name.endswith(("API_KEY", "PASSWORD", "SECRET", "TOKEN")) or (
            name.startswith(("DATABASE", "TEST_DATABASE", "REDIS"))
        ):
            return blocked()
        return original_getitem(environ, key)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(io, "open", guarded_io_open)
    monkeypatch.setattr(os, "open", guarded_os_open)
    monkeypatch.setattr(type(os.environ), "__getitem__", guarded_getitem)
    # Windows platform discovery may spawn `ver` for SDK diagnostic headers.
    # Stub only that metadata; keep all subprocess and network guards active.
    monkeypatch.setattr("openai._base_client.get_platform", lambda: "Unknown")
    monkeypatch.setattr("openai._base_client.get_architecture", lambda: "unknown")
    assert not [name for name in sys.modules if forbidden(name)]
    parent = Path(__file__).resolve().parents[1] / "conftest.py"
    assert not any(
        Path(filename).resolve() == parent
        for module in tuple(sys.modules.values())
        if isinstance(filename := getattr(module, "__file__", None), str)
    ), "Parent DB/dotenv conftest must not load"
    yield expected
    assert attempts == expected, "Unexpected or swallowed C1 external effect"
    assert not [name for name in sys.modules if forbidden(name)]
