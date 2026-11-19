"""Alembic 전용 MariaDB 연결 설정.

일반 FastAPI Settings/JWT/DB_* 및 backend/.env에 의존하지 않는다.
운영 실행 승인, Secret 혼입 감사, DB 계정 검증은 후속 Guard 책임이다.
"""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class MigrationDbSettings(BaseSettings):
    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    name: str = Field(min_length=1)
    user: str = Field(min_length=1)
    password_file: Path
    connection_timeout: int = Field(default=5, ge=1, le=30)

    model_config = SettingsConfigDict(
        env_prefix="MIGRATION_DB_",
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("host", "name", "user")
    @classmethod
    def reject_surrounding_whitespace(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("Migration DB identifier must be nonempty and unpadded")
        return value

    @property
    def connection_url(self) -> URL:
        if not self.password_file.is_absolute():
            raise ValueError("Migration DB credential file path must be absolute")

        try:
            password = self.password_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            raise ValueError("Migration DB credential file is unavailable") from None

        # Docker Compose Secret files may end with one final newline.
        password = password.removesuffix("\n").removesuffix("\r")
        if not password or any(c in password for c in ("\n", "\r", "\x00")):
            raise ValueError("Migration DB credential is invalid")

        return URL.create(
            "mysql+pymysql",
            username=self.user,
            password=password,
            host=self.host,
            port=self.port,
            database=self.name,
            query={"charset": "utf8mb4"},
        )
