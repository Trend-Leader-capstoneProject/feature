"""Offline preflight pipeline; no live DB, migration, or network allowed."""

import json
import os
import socket
from dataclasses import replace
from unittest.mock import Mock

import pytest

from scripts import migration_integration as integration
from scripts.migration_observation import DatabaseObservation, ObservedTarget


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    # Replace, rather than inherit dotenv/runtime or developer secrets.
    secret = tmp_path / "credential"
    secret.write_text("sensitive-marker", encoding="utf-8")
    root = tmp_path / "evidence"
    root.mkdir(mode=0o700)
    environ = {
        "MIGRATION_DB_HOST": "db",
        "MIGRATION_DB_PORT": "3306",
        "MIGRATION_DB_NAME": "trend",
        "MIGRATION_DB_USER": "migrator",
        "MIGRATION_DB_PASSWORD_FILE": str(secret),
        "MIGRATION_PREFLIGHT_EVIDENCE_DIR": str(root),
    }
    monkeypatch.setattr(os, "environ", environ)
    network = Mock(side_effect=AssertionError("network forbidden"))
    monkeypatch.setattr(socket, "create_connection", network)
    monkeypatch.setattr(socket.socket, "connect", network)
    target = ObservedTarget(
        "trend", "migrator@%", "12.3-MariaDB", "utf8mb4", "utf8mb4_unicode_ci"
    )
    observation = DatabaseObservation(
        target, ("a4d7c9e21f3b",), True, True, "VERSIONED_OBSERVED"
    )
    observer = Mock(return_value=observation)
    monkeypatch.setattr(integration, "observe_database", observer)
    yield environ, root, observer, network
    network.assert_not_called()


def test_normal_observation_is_persisted_before_exit_zero(pipeline, capsys):
    _, root, observer, _ = pipeline
    assert integration.run_preflight() == (0, ())
    observer.assert_called_once()
    files = list(root.glob("*/report.json"))
    assert len(files) == 1
    assert json.loads(files[0].read_text())["inspection_status"] == "OBSERVED"
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "key",
    [
        "DATABASE_URL",
        "db_host",
        "API_DB_PASSWORD_FILE",
        "JWT_SECRET_KEY",
        "MARIADB_ROOT_PASSWORD",
        "MIGRATION_DB_PASSWORD",
        "MIGRATION_DB_UNKNOWN",
    ],
)
@pytest.mark.parametrize("value", ["", "sensitive-marker"])
def test_conflict_does_not_read_files_or_observe(pipeline, monkeypatch, key, value):
    from pathlib import Path

    environ, root, observer, _ = pipeline
    environ[key] = value
    read = Mock(side_effect=AssertionError("secret read before audit"))
    available = Mock(side_effect=AssertionError("root checked before audit"))
    writer = Mock(side_effect=AssertionError("writer before audit"))
    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr(integration, "evidence_root_available", available)
    monkeypatch.setattr(integration, "write_evidence", writer)
    assert integration.run_preflight() == (4, ("ENV_CONFLICT",))
    for call in (observer, read, available, writer):
        call.assert_not_called()
    assert list(root.iterdir()) == []


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("MIGRATION_DB_PORT", "invalid"),
        ("MIGRATION_DB_PORT", "0"),
        ("MIGRATION_DB_CONNECTION_TIMEOUT", "31"),
        ("MIGRATION_DB_USER", " padded "),
        ("MIGRATION_DB_PASSWORD_FILE", "relative"),
        ("MIGRATION_DB_HOST", ""),
        ("MIGRATION_PREFLIGHT_EVIDENCE_DIR", ""),
    ],
)
def test_invalid_settings_no_observation(pipeline, key, value):
    environ, root, observer, _ = pipeline
    environ[key] = value
    assert integration.run_preflight() == (4, ("SETTINGS_INVALID",))
    observer.assert_not_called()
    assert list(root.iterdir()) == []


@pytest.mark.parametrize("kind", ["missing", "relative", "file"])
def test_root_rejected_before_observation(pipeline, kind):
    environ, root, observer, _ = pipeline
    environ["MIGRATION_PREFLIGHT_EVIDENCE_DIR"] = {
        "missing": str(root / "missing"),
        "relative": "relative",
        "file": environ["MIGRATION_DB_PASSWORD_FILE"],
    }[kind]
    assert integration.run_preflight() == (4, ("EVIDENCE_WRITE_FAILED",))
    observer.assert_not_called()
    assert list(root.iterdir()) == []


@pytest.mark.parametrize(
    ("change", "code", "status"),
    [
        (
            {
                "schema_state": "UNVERSIONED_EMPTY_CANDIDATE",
                "current_revisions": (),
                "version_table_visible": False,
                "business_objects_visible": False,
            },
            0,
            "OBSERVED",
        ),
        (
            {
                "schema_state": "INDETERMINATE",
                "current_revisions": ("unknown",),
                "reason_codes": ("SCHEMA_INDETERMINATE",),
            },
            3,
            "INDETERMINATE",
        ),
    ],
)
def test_observation_states_saved(pipeline, change, code, status):
    _, root, observer, _ = pipeline
    observer.return_value = replace(observer.return_value, **change)
    assert integration.run_preflight()[0] == code
    data = json.loads(next(root.glob("*/report.json")).read_text())
    assert data["inspection_status"] == status
    assert data["image_identity_verification_status"] == "NOT_VERIFIED"


@pytest.mark.parametrize(
    "reason",
    [
        "SETTINGS_INVALID",
        "DB_CONNECTION_FAILED",
        "READ_ONLY_NOT_ESTABLISHED",
        "OBSERVATION_FAILED",
    ],
)
def test_error_observation_is_saved(pipeline, reason):
    _, root, observer, _ = pipeline
    observer.return_value = DatabaseObservation(reason_codes=(reason,))
    assert integration.run_preflight() == (4, (reason,))
    data = json.loads(next(root.glob("*/report.json")).read_text())
    assert data["inspection_status"] == "ERROR"
    assert all(value is None for value in data["observed_target"].values())
    assert all(value is None for value in data["checks"].values())


@pytest.mark.parametrize("kind", ["contradiction", "exception"])
def test_invalid_or_raised_observation_gets_safe_error(pipeline, kind, capsys, caplog):
    _, root, observer, _ = pipeline
    if kind == "exception":
        observer.side_effect = RuntimeError(
            "sensitive-marker mysql://user:password@host"
        )
    else:
        observer.return_value = replace(
            observer.return_value, reason_codes=("OBSERVATION_FAILED",)
        )
    assert integration.run_preflight() == (4, ("OBSERVATION_FAILED",))
    data = next(root.glob("*/report.json")).read_text()
    assert json.loads(data)["inspection_status"] == "ERROR"
    captured = capsys.readouterr()
    assert "sensitive-marker" not in data + captured.out + captured.err + caplog.text


@pytest.mark.parametrize("status", ["OBSERVED", "INDETERMINATE", "ERROR"])
@pytest.mark.parametrize("failure", ["return", "exception", "sync"])
def test_storage_failure_has_priority(pipeline, monkeypatch, status, failure):
    from scripts import migration_evidence as evidence

    _, _, observer, _ = pipeline
    if status == "ERROR":
        observer.return_value = DatabaseObservation(
            reason_codes=("DB_CONNECTION_FAILED",)
        )
    elif status == "INDETERMINATE":
        observer.return_value = replace(
            observer.return_value,
            schema_state="INDETERMINATE",
            current_revisions=("unknown",),
            reason_codes=("SCHEMA_INDETERMINATE",),
        )
    if failure == "sync":
        monkeypatch.setattr(
            evidence, "_sync_directory", Mock(side_effect=OSError("sensitive-marker"))
        )
    else:
        writer = Mock(return_value=evidence.EvidenceWriteResult())
        if failure == "exception":
            writer.side_effect = OSError("sensitive-marker")
        monkeypatch.setattr(integration, "write_evidence", writer)
    assert integration.run_preflight() == (4, ("EVIDENCE_WRITE_FAILED",))


def test_duplicate_id_preserves_report(pipeline, monkeypatch):
    from scripts import migration_report

    _, root, _, _ = pipeline
    monkeypatch.setattr(
        migration_report,
        "new_evidence_id",
        lambda: "c66363da-35db-41ac-9748-20c0a2e76bca",
    )
    assert integration.run_preflight()[0] == 0
    path = next(root.glob("*/report.json"))
    original = path.read_bytes()
    assert integration.run_preflight() == (4, ("EVIDENCE_WRITE_FAILED",))
    assert path.read_bytes() == original


def test_writer_finishes_before_success(pipeline, monkeypatch, capsys):
    _, _, observer, _ = pipeline
    writer = integration.write_evidence
    calls = []

    def recording(root, data):
        observer.assert_called_once()
        assert capsys.readouterr().out == ""
        calls.append("writing")
        result = writer(root, data)
        assert result.success
        calls.append("persisted")
        return result

    monkeypatch.setattr(integration, "write_evidence", recording)
    assert integration.run_preflight()[0] == 0
    assert calls == ["writing", "persisted"]


@pytest.mark.parametrize(
    ("case", "exit_code", "reason"),
    [
        ("normal", 0, None),
        ("empty", 0, None),
        ("unknown", 3, "SCHEMA_INDETERMINATE"),
        ("null_revision", 3, "SCHEMA_INDETERMINATE"),
        ("mismatch", 3, "TARGET_MISMATCH"),
        ("connect", 4, "DB_CONNECTION_FAILED"),
        ("readonly", 4, "READ_ONLY_NOT_ESTABLISHED"),
        ("read", 4, "OBSERVATION_FAILED"),
        ("rollback", 4, "OBSERVATION_FAILED"),
        ("close", 4, "OBSERVATION_FAILED"),
        ("dispose", 4, "OBSERVATION_FAILED"),
    ],
)
def test_guard_through_real_observer_and_writer_offline(
    pipeline, monkeypatch, capsys, caplog, case, exit_code, reason
):
    from types import SimpleNamespace

    from scripts import migration_observation as observation
    from scripts.migration_guard import main

    _, root, _, _ = pipeline
    monkeypatch.setattr(integration, "observe_database", observation.observe_database)
    engine = Mock()
    engine.pool.cleanup_failed = False
    connection = Mock()
    engine.connect.return_value = connection
    factory = Mock(return_value=engine)
    monkeypatch.setattr(observation, "create_engine", factory)
    marker = "sensitive-marker mysql://user:password@host"
    calls = []

    def sql(statement):
        calls.append(statement)
        if (case == "readonly" and statement == observation.START_READ_ONLY) or (
            case == "read" and statement == observation.DEFAULTS_SQL
        ):
            raise RuntimeError(marker)
        rows = {
            observation.START_READ_ONLY: [],
            observation.TARGET_SQL: [
                (
                    "other" if case == "mismatch" else "trend",
                    "migrator@%",
                    "12.3-MariaDB",
                )
            ],
            observation.DEFAULTS_SQL: [("utf8mb4", "utf8mb4_unicode_ci")],
            observation.OBJECTS_SQL: []
            if case == "empty"
            else [("TABLE", "alembic_version")],
            observation.REVISIONS_SQL: [
                (
                    "unknown"
                    if case == "unknown"
                    else None
                    if case == "null_revision"
                    else "a4d7c9e21f3b",
                )
            ],
        }[statement]
        return SimpleNamespace(fetchall=lambda: rows, close=lambda: None)

    connection.exec_driver_sql.side_effect = sql
    if case == "connect":
        engine.connect.side_effect = RuntimeError(marker)
    if case in {"rollback", "close"}:
        getattr(connection, case).side_effect = RuntimeError(marker)
    if case == "dispose":
        engine.dispose.side_effect = RuntimeError(marker)

    assert main(["preflight"]) == exit_code
    factory.assert_called_once()
    engine.connect.assert_called_once()
    engine.dispose.assert_called_once()
    if case != "connect":
        assert calls[0] == observation.START_READ_ONLY
        connection.rollback.assert_called_once()
        connection.close.assert_called_once()
    assert all(statement in observation.ALLOWED_SQL for statement in calls)
    data_text = next(root.glob("*/report.json")).read_text()
    data = json.loads(data_text)
    assert (
        data["inspection_status"]
        == {0: "OBSERVED", 3: "INDETERMINATE", 4: "ERROR"}[exit_code]
    )
    assert data["reason_codes"] == ([] if reason is None else [reason])
    captured = capsys.readouterr()
    assert captured.out == ("OBSERVED\n" if exit_code == 0 else "")
    assert captured.err == ("" if reason is None else reason + "\n")
    assert (
        "sensitive-marker" not in data_text + captured.out + captured.err + caplog.text
    )


def test_windows_directory_sync_false_does_not_create_new_policy(pipeline, monkeypatch):
    from scripts import migration_evidence as evidence

    monkeypatch.setattr(evidence, "_sync_directory", lambda _: False)
    assert integration.run_preflight() == (0, ())


def test_output_failure_keeps_saved_evidence(pipeline, monkeypatch):
    from scripts import migration_guard

    _, root, observer, _ = pipeline
    monkeypatch.setattr(
        migration_guard,
        "print",
        Mock(side_effect=BrokenPipeError("sensitive-marker")),
        raising=False,
    )
    assert migration_guard.main(["preflight"]) == 4
    observer.assert_called_once()
    data = json.loads(next(root.glob("*/report.json")).read_text())
    assert data["inspection_status"] == "OBSERVED"
    assert not list(root.glob("*/report.tmp"))


def test_sensitive_metadata_never_persisted(pipeline, capsys, caplog):
    _, root, observer, _ = pipeline
    observer.return_value = replace(
        observer.return_value,
        observed_target=replace(
            observer.return_value.observed_target,
            server_version="mysql://user:sensitive-marker@host",
        ),
    )
    assert integration.run_preflight() == (4, ("EVIDENCE_WRITE_FAILED",))
    assert list(root.iterdir()) == []
    captured = capsys.readouterr()
    assert "sensitive-marker" not in captured.out + captured.err + caplog.text


@pytest.mark.parametrize("credential", [None, "", "line1\nline2", "nul\x00byte"])
def test_bad_secret_prevents_db_and_evidence(pipeline, credential):
    from pathlib import Path

    environ, root, observer, _ = pipeline
    path = Path(environ["MIGRATION_DB_PASSWORD_FILE"])
    if credential is None:
        path.unlink()
    else:
        path.write_text(credential, encoding="utf-8")
    assert integration.run_preflight() == (4, ("SETTINGS_INVALID",))
    observer.assert_not_called()
    assert list(root.iterdir()) == []


def test_lowercase_inputs_complete_pipeline(pipeline):
    environ, _, observer, _ = pipeline
    data = {key.lower(): value for key, value in environ.items()}
    environ.clear()
    environ.update(data)
    assert integration.run_preflight() == (0, ())
    observer.assert_called_once()
