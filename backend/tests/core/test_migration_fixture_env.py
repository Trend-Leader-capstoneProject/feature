"""기존 통합 테스트 Fixture가 전용 Migration 자격 증명을 전달하는지 검사."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


def load_fixture_module():
    path = Path(__file__).resolve().parents[1] / "conftest.py"
    spec = spec_from_file_location("migration_test_fixtures", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_fixture_uses_test_database_and_cleans_secret(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    test_url = (
        "mysql+pymysql://migration_test_user:pa%40ss@"
        "127.0.0.1:3307/trend_leader_test"
    )
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://root:wrong@prod/production")
    monkeypatch.setenv("MIGRATION_DB_USER", "root")
    secret_file: Path | None = None

    def verify_command(_args, **kwargs):
        nonlocal secret_file
        env = kwargs["env"]
        assert "DATABASE_URL" not in env
        assert env["MIGRATION_DB_HOST"] == "127.0.0.1"
        assert env["MIGRATION_DB_PORT"] == "3307"
        assert env["MIGRATION_DB_NAME"] == "trend_leader_test"
        assert env["MIGRATION_DB_USER"] == "migration_test_user"
        secret_file = Path(env["MIGRATION_DB_PASSWORD_FILE"])
        assert secret_file.read_text(encoding="utf-8") == "pa@ss"

    fixtures = load_fixture_module()
    monkeypatch.setattr(fixtures.subprocess, "run", verify_command)
    value = fixtures.migrated_test_database.__wrapped__(
        test_url, tmp_path_factory
    )
    assert value == test_url
    assert secret_file is not None and not secret_file.exists()
