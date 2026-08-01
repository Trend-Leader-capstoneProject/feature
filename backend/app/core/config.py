from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
# 현재 파일: backend/app/core/config.py
# parents[0] = core
# parents[1] = app
# parents[2] = backend

RESOURCES_DIR = BASE_DIR / "app" / "resources"


class Settings(BaseSettings):
    # App
    app_name: str = "Trend Leader API"
    app_env: str = "local"
    debug: bool = True
    api_prefix: str = "/api"

    # Database
    db_host: str = "127.0.0.1"
    db_port: int = Field(default=3306, ge=1, le=65535)
    db_name: str = "trend_leader"
    db_user: str = "trend_user"
    db_password: str = "trend_pass"

    # 운영 환경처럼 완성된 DB URL을 직접 주입할 때 사용한다.
    # 값이 존재하면 아래 DB_HOST, DB_PORT 등의 개별 설정보다 우선한다.
    database_url: str | None = None

    # SQLAlchemy Connection Pool
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)
    db_pool_timeout: int = Field(default=30, ge=1)
    db_pool_recycle: int = Field(default=1800, ge=1)
    db_connection_timeout: int = Field(default=5, ge=1)

    # JWT
    jwt_secret_key: str = Field(..., min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # OAuth
    google_client_id: str | None = None
    google_client_secret: str | None = None

    # AI
    ai_provider: str = "mock"
    openai_api_key: str | None = None
    gemini_api_key: str | None = None

    # CORS
    cors_origins: str = "http://localhost:8081"

    # Resources
    resources_dir: Path = RESOURCES_DIR

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def sync_database_url(self) -> str:
        """
        SQLAlchemy 동기식 데이터베이스 URL을 반환한다.

        DATABASE_URL이 설정되어 있으면 해당 값을 우선 사용하고,
        없으면 DB_HOST 등의 개별 설정값으로 URL을 생성한다.
        """

        if self.database_url:
            return self.database_url

        encoded_user = quote_plus(self.db_user)
        encoded_password = quote_plus(self.db_password)

        return (
            f"mysql+pymysql://{encoded_user}:{encoded_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            "?charset=utf8mb4"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
