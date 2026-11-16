"""C2 only: run with --confcutdir=tests/responses_web_search_c2."""

import builtins
import importlib.abc
import io
import os
import socket
import subprocess
import sys
from pathlib import Path

import httpx2
import pytest
from openai.resources.responses import Responses
from support import MockEndpoint

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
            raise AssertionError("C2 operational import forbidden")
        return None


_import_guard = NoOperationalImports()
sys.meta_path.insert(0, _import_guard)


@pytest.fixture
def endpoint():
    return MockEndpoint()


@pytest.fixture
def http_client(endpoint):
    with httpx2.Client(
        transport=httpx2.MockTransport(endpoint.handle), trust_env=False,
    ) as client:
        yield client


@pytest.fixture
def sdk_responses(monkeypatch):
    """Observe real SDK returns, with no success substitute."""
    returned = []
    original_create = Responses.create

    def observe(*args, **kwargs):
        result = original_create(*args, **kwargs)
        returned.append(result)
        return result

    monkeypatch.setattr(Responses, "create", observe)
    return returned


def pytest_sessionfinish(session, exitstatus):
    if _import_guard in sys.meta_path:
        sys.meta_path.remove(_import_guard)


@pytest.fixture(autouse=True)
def isolated_io(monkeypatch):
    """Allow normal package reads; record even swallowed external I/O attempts."""
    attempts = []
    expected = []

    def blocked(*args, **kwargs):
        attempts.append("blocked")
        raise AssertionError("C2 external effect forbidden")

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

    def secret_file(file):
        if not isinstance(file, (str, bytes, os.PathLike)):
            return False
        path = Path(os.fsdecode(file))
        return path.name.startswith(".env") or any(
            part in {".aws", ".ssh"} for part in path.parts
        )

    def guard_open(original):
        def guarded(file, *args, **kwargs):
            if secret_file(file):
                return blocked()
            return original(file, *args, **kwargs)
        return guarded

    monkeypatch.setattr(builtins, "open", guard_open(builtins.open))
    monkeypatch.setattr(io, "open", guard_open(io.open))
    monkeypatch.setattr(os, "open", guard_open(os.open))
    # Replace the mapping without enumerating/reading real environment values.
    # SDK optional org/project/admin/webhook defaults may read this empty mapping.
    monkeypatch.setattr(os, "environ", {})
    # Windows SDK diagnostic headers may otherwise run `ver` via a subprocess.
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
    assert attempts == expected, "Unexpected or swallowed C2 external effect"
    assert not [name for name in sys.modules if forbidden(name)]
