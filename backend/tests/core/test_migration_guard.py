"""Phase B-1 Guard: no invocation may connect, preflight, or run Alembic."""

from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.migration_guard import (
    DENY_DEFAULT,
    EXIT_DENIED,
    INVALID_MODE,
    MODE_NOT_ENABLED,
    main,
)


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        ([], DENY_DEFAULT),
        (["deny"], DENY_DEFAULT),
        (["preflight"], MODE_NOT_ENABLED),
        (["apply"], MODE_NOT_ENABLED),
        (["upgrade", "head"], INVALID_MODE),
        (["alembic", "upgrade", "head"], INVALID_MODE),
        (["downgrade"], INVALID_MODE),
        (["stamp", "head"], INVALID_MODE),
        (["revision"], INVALID_MODE),
        (["--help"], INVALID_MODE),
        (["deny", "--force"], INVALID_MODE),
        (["apply", "--approval", "example.json"], INVALID_MODE),
        (["preflight", "--json"], INVALID_MODE),
    ],
)
def test_guard_fails_closed(argv, expected, capsys):
    assert main(argv) == EXIT_DENIED
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"{expected}\n"


def test_default_uses_process_arguments(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["migration_guard"])
    assert main() == EXIT_DENIED
    assert capsys.readouterr().err == f"{DENY_DEFAULT}\n"


def test_sensitive_argument_and_environment_not_echoed(monkeypatch, capsys):
    marker = "example-super-secret-not-a-real-password"
    monkeypatch.setenv("MIGRATION_DB_PASSWORD", marker)
    assert main(["apply", f"--password={marker}"]) == EXIT_DENIED
    captured = capsys.readouterr()
    assert marker not in (captured.out + captured.err)
    assert captured.err == f"{INVALID_MODE}\n"


def test_guard_never_uses_network_or_subprocess(monkeypatch, capsys):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Guard attempted an external action")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    for mode in ([], ["deny"], ["preflight"], ["apply"]):
        assert main(mode) == EXIT_DENIED
    capsys.readouterr()


def test_python_module_execution_is_denied():
    backend_dir = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "scripts.migration_guard"],
        cwd=backend_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == EXIT_DENIED
    assert result.stdout == ""
    assert result.stderr.strip() == DENY_DEFAULT
