from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.migration_db_config import MigrationDbSettings

FIELDS = ("HOST", "PORT", "NAME", "USER", "PASSWORD_FILE", "CONNECTION_TIMEOUT")


def configure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    password: str = "p@ss:/#word",
) -> Path:
    for field in FIELDS:
        monkeypatch.delenv(f"MIGRATION_DB_{field}", raising=False)
    secret = tmp_path / "migration_password"
    secret.write_text(password + "\n", encoding="utf-8")
    for k, v in {
        "HOST": "db",
        "PORT": "3306",
        "NAME": "trend_leader_test",
        "USER": "trend_migration",
        "PASSWORD_FILE": str(secret),
    }.items():
        monkeypatch.setenv(f"MIGRATION_DB_{k}", v)
    return secret


def test_migration_settings_without_jwt_or_app_settings(monkeypatch, tmp_path):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    configure(monkeypatch, tmp_path)
    settings = MigrationDbSettings(_env_file=None)
    assert settings.connection_url.username == "trend_migration"
    assert settings.connection_url.host == "db"


def test_legacy_database_url_and_runtime_db_settings_not_used(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://root:wrong@prod/not_allowed")
    monkeypatch.setenv("DB_USER", "root")
    monkeypatch.setenv("JWT_SECRET_KEY", "another_value")
    url = MigrationDbSettings(_env_file=None).connection_url
    assert url.username == "trend_migration"
    assert url.database == "trend_leader_test"
    assert url.host == "db"


def test_secret_special_characters_and_no_password_in_repr(monkeypatch, tmp_path):
    secret = configure(monkeypatch, tmp_path)
    settings = MigrationDbSettings(_env_file=None)
    url = settings.connection_url
    assert url.password == "p@ss:/#word"
    assert url.query["charset"] == "utf8mb4"
    assert "p@ss" not in str(url)
    assert "p@ss" not in repr(settings)
    assert str(secret) in repr(settings)


@pytest.mark.parametrize("missing", ["HOST", "PORT", "NAME", "USER", "PASSWORD_FILE"])
def test_missing_migration_setting_fails(monkeypatch, tmp_path, missing):
    configure(monkeypatch, tmp_path)
    monkeypatch.delenv(f"MIGRATION_DB_{missing}")
    with pytest.raises(ValidationError):
        MigrationDbSettings(_env_file=None)


@pytest.mark.parametrize("content", ["", "line1\nline2", "password\x00part"])
def test_invalid_password_file_fails_without_leaking_value(
    monkeypatch, tmp_path, content
):
    secret = configure(monkeypatch, tmp_path)
    secret.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="credential is invalid") as exc:
        MigrationDbSettings(_env_file=None).connection_url
    if content:
        assert content not in str(exc.value)


def test_missing_secret_file_fails(monkeypatch, tmp_path):
    secret = configure(monkeypatch, tmp_path)
    secret.unlink()
    with pytest.raises(ValueError, match="credential file is unavailable"):
        MigrationDbSettings(_env_file=None).connection_url


def test_relative_secret_path_rejected(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    monkeypatch.setenv("MIGRATION_DB_PASSWORD_FILE", "relative-secret")
    with pytest.raises(ValueError, match="must be absolute"):
        MigrationDbSettings(_env_file=None).connection_url


@pytest.mark.parametrize("value", [" ", " db", "db "])
def test_invalid_host_rejected(monkeypatch, tmp_path, value):
    configure(monkeypatch, tmp_path)
    monkeypatch.setenv("MIGRATION_DB_HOST", value)
    with pytest.raises(ValidationError):
        MigrationDbSettings(_env_file=None)


def test_invalid_port_rejected(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    monkeypatch.setenv("MIGRATION_DB_PORT", "0")
    with pytest.raises(ValidationError):
        MigrationDbSettings(_env_file=None)


def test_no_dotenv_fallback(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    (tmp_path / ".env").write_text("MIGRATION_DB_HOST=overridden\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert MigrationDbSettings(_env_file=None).host == "db"
