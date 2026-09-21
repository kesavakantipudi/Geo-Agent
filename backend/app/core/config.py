"""Application settings loaded from the environment / `.env`.

All environment variables are namespaced with the `GEOAGENT_` prefix.
Unknown `GEOAGENT_` variables (for example the frontend's
`NEXT_PUBLIC_*`) are ignored.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """GeoAgent backend settings.

    Values are read from environment variables (prefix ``GEOAGENT_``) and,
    when run from the ``backend/`` directory, from a local ``.env`` file.
    """

    model_config = SettingsConfigDict(
        env_prefix="GEOAGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = "development"  # development | test | production
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "geoagent"
    db_user: str = "geoagent"
    db_password: str = ""
    db_schema: str = "public"
    database_url: str | None = None  # optional full SQLAlchemy URL override

    # Authentication
    auth_secret_key: str = ""
    auth_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # Google sign-in (reserved for a later phase; must be supplied via env)
    google_client_id: str = ""
    google_client_secret: str = ""

    # HTTP / CORS
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # SQLAlchemy echo (debug only)
    db_echo: bool = False

    @model_validator(mode="after")
    def _validate_secret_key(self) -> Settings:
        if self.app_env != "test" and (not self.auth_secret_key or len(self.auth_secret_key) < 32):
            raise ValueError(
                "GEOAGENT_AUTH_SECRET_KEY must be set to at least 32 characters "
                "in non-test environments. Generate one with: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return self

    @property
    def sqlalchemy_database_url(self) -> str:
        """Full SQLAlchemy URL, either explicit or composed from parts."""
        if self.database_url:
            return self.database_url
        password = self.db_password or ""
        return f"postgresql+psycopg://{self.db_user}:{password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
