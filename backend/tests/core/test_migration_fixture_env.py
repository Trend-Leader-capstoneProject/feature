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


def allow_test_target(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test-only independent target values, never copied from the URL."""
    for key, value in {
        "HOST": "127.0.0.1",
        "PORT": "3307",
        "DATABASE": "trend_leader_test",
        "USER": "migration_test_user",
    }.items():
        monkeypatch.setenv(f"TEST_MIGRATION_ALLOWED_{key}", value)


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
    allow_test_target(monkeypatch)
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


@pytest.mark.parametrize("missing", ["HOST", "PORT", "DATABASE", "USER"])
def test_migration_fixture_denies_missing_approval_before_alembic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
    missing: str,
) -> None:
    allow_test_target(monkeypatch)
    monkeypatch.delenv(f"TEST_MIGRATION_ALLOWED_{missing}", raising=False)
    fixtures = load_fixture_module()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("No secret file or Alembic call is allowed")

    monkeypatch.setattr(tmp_path_factory, "mktemp", forbidden)
    monkeypatch.setattr(fixtures.subprocess, "run", forbidden)

    with pytest.raises(RuntimeError, match="requires explicit target approval"):
        fixtures.migrated_test_database.__wrapped__(
            "mysql+pymysql://migration_test_user:secret@"
            "127.0.0.1:3307/trend_leader_test",
            tmp_path_factory,
        )


@pytest.mark.parametrize(
    ("key", "wrong_value"),
    [
        ("HOST", "localhost"),
        ("PORT", "3308"),
        ("DATABASE", "different_test_db"),
        ("USER", "another_user"),
    ],
)
def test_migration_fixture_denies_mismatched_target_before_alembic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
    key: str,
    wrong_value: str,
) -> None:
    allow_test_target(monkeypatch)
    monkeypatch.setenv(f"TEST_MIGRATION_ALLOWED_{key}", wrong_value)
    fixtures = load_fixture_module()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("No secret file or Alembic call is allowed")

    monkeypatch.setattr(tmp_path_factory, "mktemp", forbidden)
    monkeypatch.setattr(fixtures.subprocess, "run", forbidden)

    with pytest.raises(RuntimeError, match="target differs from approval"):
        fixtures.migrated_test_database.__wrapped__(
            "mysql+pymysql://migration_test_user:secret@"
            "127.0.0.1:3307/trend_leader_test",
            tmp_path_factory,
        )


@pytest.mark.parametrize(
    "test_url",
    [
        "mysql+pymysql://migration_test_user:secret@"
        "example.org:3307/trend_leader_test",
        "mysql+pymysql://migration_test_user:secret@"
        "127.0.0.1:3306/trend_leader_test",
        "mysql+pymysql://migration_test_user:secret@"
        "127.0.0.1/trend_leader_test",
        "mysql+pymysql://migration_test_user:secret@"
        "127.0.0.1:3307/production",
        "mysql+pymysql://migration_test_user@"
        "127.0.0.1:3307/trend_leader_test",
        "sqlite:///trend_leader_test",
    ],
)
def test_migration_fixture_denies_nonisolated_url_before_alembic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
    test_url: str,
) -> None:
    allow_test_target(monkeypatch)
    fixtures = load_fixture_module()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("No secret file or Alembic call is allowed")

    monkeypatch.setattr(tmp_path_factory, "mktemp", forbidden)
    monkeypatch.setattr(fixtures.subprocess, "run", forbidden)

    with pytest.raises(RuntimeError, match="requires a local isolated test target"):
        fixtures.migrated_test_database.__wrapped__(test_url, tmp_path_factory)


def test_migration_target_allows_explicitly_matched_3308(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    allow_test_target(monkeypatch)
    monkeypatch.setenv("TEST_MIGRATION_ALLOWED_PORT", "3308")
    fixtures = load_fixture_module()
    invoked = []

    def fake_alembic(_args, **kwargs):
        invoked.append(kwargs["env"]["MIGRATION_DB_PORT"])

    monkeypatch.setattr(fixtures.subprocess, "run", fake_alembic)
    url = (
        "mysql+pymysql://migration_test_user:secret@"
        "127.0.0.1:3308/trend_leader_test"
    )
    assert fixtures.migrated_test_database.__wrapped__(
        url, tmp_path_factory
    ) == url
    assert invoked == ["3308"]
