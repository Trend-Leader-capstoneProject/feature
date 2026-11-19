"""Guard accepts only exact preflight; every other refusal stays intact."""

from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

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
    for mode in ([], ["deny"], ["apply"]):
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


def test_preflight_uses_completed_pipeline(monkeypatch, capsys):
    from scripts import migration_integration

    pipeline = Mock(return_value=(0, ()))
    monkeypatch.setattr(migration_integration, "run_preflight", pipeline)
    assert main(["preflight"]) == 0
    pipeline.assert_called_once_with()
    assert capsys.readouterr().out == "OBSERVED\n"


@pytest.mark.parametrize(
    ("code", "reason"), [(3, "SCHEMA_INDETERMINATE"), (4, "EVIDENCE_WRITE_FAILED")]
)
def test_preflight_fixed_error_output(monkeypatch, capsys, code, reason):
    from scripts import migration_integration

    monkeypatch.setattr(
        migration_integration, "run_preflight", lambda: (code, (reason,))
    )
    assert main(["preflight"]) == code
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == reason + "\n"


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["deny"],
        ["apply"],
        ["preflight", "--json"],
        ["PREFLIGHT"],
        ["preflight "],
        ["upgrade", "head"],
        ["preflight", "preflight"],
    ],
)
def test_invalid_cli_no_environment_files_network_or_imports(monkeypatch, capsys, argv):
    import builtins
    import os

    class ForbiddenEnvironment(dict):
        def keys(self):
            raise AssertionError("environment read")

        def __iter__(self):
            raise AssertionError("environment read")

        def __getitem__(self, key):
            raise AssertionError("environment read")

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        assert name != "scripts.migration_integration"
        return original_import(name, *args, **kwargs)

    forbidden = Mock(side_effect=AssertionError("unexpected I/O"))
    with monkeypatch.context() as patch:
        patch.setattr(os, "environ", ForbiddenEnvironment())
        patch.setattr(builtins, "__import__", guarded_import)
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(Path, "open", forbidden)
        patch.setattr(Path, "stat", forbidden)
        patch.setattr(Path, "lstat", forbidden)
        patch.setattr(Path, "mkdir", forbidden)
        patch.setattr(socket.socket, "connect", forbidden)
        patch.setattr(socket, "create_connection", forbidden)
        assert main(argv) == 2
    forbidden.assert_not_called()
    capsys.readouterr()


def test_pipeline_exception_not_exposed(monkeypatch, capsys, caplog):
    from scripts import migration_integration

    monkeypatch.setattr(
        migration_integration,
        "run_preflight",
        Mock(side_effect=RuntimeError("sensitive-marker mysql://user:password@host")),
    )
    assert main(["preflight"]) == 4
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "OBSERVATION_FAILED\n"
    assert "sensitive-marker" not in caplog.text
