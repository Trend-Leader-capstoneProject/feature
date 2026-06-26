from functools import lru_cache
from pathlib import Path

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
    db_port: int = 3306
    db_name: str = "trend_leader"
    db_user: str = "trend_user"
    db_password: str = "trend_pass"
    database_url: str

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
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()