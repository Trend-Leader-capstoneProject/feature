"""Legacy account Migration apply must fail closed until safely redesigned.

These tests deliberately use no DB fixture, network, Docker or Alembic DDL.
"""

import json

import pytest

from scripts import verify_account_migration as migration


@pytest.mark.parametrize("conflicting_environment", [False, True])
def test_direct_apply_is_denied_before_target_read_or_any_ddl(
    monkeypatch: pytest.MonkeyPatch, conflicting_environment: bool
) -> None:
    if conflicting_environment:
        monkeypatch.setenv("MIGRATION_DB_HOST", "not-the-test-db.example")
        monkeypatch.setenv("MIGRATION_DB_PORT", "3306")
        monkeypatch.setenv("MIGRATION_DB_NAME", "not_the_test_database")

    def unexpected_action(*_args, **_kwargs):
        raise AssertionError("Legacy apply attempted database/target access")

    monkeypatch.setattr(migration, "test_url", unexpected_action)
    monkeypatch.setattr(migration, "create_engine", unexpected_action)
    monkeypatch.setattr(migration.command, "upgrade", unexpected_action)
    monkeypatch.setattr(migration.command, "downgrade", unexpected_action)
    monkeypatch.setattr(migration.command, "stamp", unexpected_action)

    with pytest.raises(RuntimeError, match="ACCOUNT_MIGRATION_APPLY_DISABLED"):
        migration.verify(apply=True)


def test_cli_apply_fails_with_exit_two_without_running_verifier(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def unexpected_action(*_args, **_kwargs):
        raise AssertionError("Legacy CLI attempted verification")

    monkeypatch.setattr(migration, "verify", unexpected_action)
    with pytest.raises(SystemExit) as exc_info:
        migration.main(["--apply"])

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "ACCOUNT_MIGRATION_APPLY_DISABLED" in captured.err


def test_read_only_cli_remains_available_without_db_access(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    observed = []

    def fake_verify(apply=False):
        observed.append(apply)
        return {"eligible_empty_test_database": True, "applied": False}

    monkeypatch.setattr(migration, "verify", fake_verify)
    assert migration.main([]) == 0
    assert observed == [False]
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "eligible_empty_test_database": True,
        "applied": False,
    }
    assert captured.err == ""
