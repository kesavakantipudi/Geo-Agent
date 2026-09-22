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

    # Place geocoding (Phase 3). Provider is pluggable via env; default is Photon.
    geocoder_provider: str = "photon"  # "photon" | "none" (disable)
    geocoder_photon_url: str = "https://photon.komoot.io/api"
    geocoder_timeout_seconds: float = 10.0
    geocoder_rate_per_second: float = 1.0  # 0 disables throttling
    geocoder_user_agent: str = "GeoAgent/0.1 (Phase 3 development)"
    geocoder_max_results: int = 8

    # Geometry validation (Phase 3)
    max_geometry_points: int = 2000
    # Analysis sessions must not target an unreasonably distant future.
    analysis_max_future_years: int = 10

    # Satellite scene discovery (Phase 4). Providers are pluggable via env;
    # "none" (or an empty list) disables scene discovery.
    satellite_enabled_providers: str = "planetary-computer"  # comma-separated
    satellite_max_scenes_per_provider: int = 40
    satellite_max_cloud_cover: float = 100.0
    satellite_timeout_seconds: float = 20.0
    satellite_rate_per_second: float = 0.0  # 0 disables throttling
    satellite_user_agent: str = "GeoAgent/0.1 (Phase 4 development)"

    # Microsoft Planetary Computer (default provider). STAC search is key-less;
    # data assets are signed on demand through the Data Authentication (SAS) API.
    planetary_computer_stac_url: str = "https://planetarycomputer.microsoft.com/api/stac/v1"
    planetary_computer_sas_url: str = "https://planetarycomputer.microsoft.com/api/sas/v1"

    # Copernicus Data Space Ecosystem (optional; discovered via its STAC API).
    cdse_stac_url: str = "https://stac.dataspace.copernicus.eu/v1"
    cdse_token_url: str = (
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    )
    cdse_client_id: str = "cdse-public"
    cdse_username: str = ""  # leave empty to skip CDSE downloads
    cdse_password: str = ""  # never committed to the repository
    cdse_totp: str = ""  # optional one-time password for 2FA-protected accounts

    # Bounded, on-demand asset retrieval.
    retrieval_storage_dir: str = "var/satellite"
    retrieval_max_bytes: int = 200 * 1024 * 1024  # 200 MiB per asset
    retrieval_max_assets_per_scene: int = 8
    retrieval_url_allowlist: str = ""  # extra allowed download hosts, comma-separated
    retrieval_timeout_seconds: float = 60.0

    # Weather & environmental data (Phase 5). Providers are pluggable via env;
    # "none" (or an empty list) disables weather retrieval. The default provider
    # is Open-Meteo (a non-commercial service: <10 000 calls/day, no API key,
    # attribution required — "Weather data by Open-Meteo.com"). UA + attribution
    # strings are configured so responses always carry provenance, and the
    # non-commercial flag is surfaced to operators.
    weather_enabled_providers: str = "openmeteo"  # comma-separated
    weather_max_points_per_aoi: int = 20
    weather_max_variables: int = 20
    weather_timeout_seconds: float = 30.0
    weather_rate_per_second: float = 0.0  # 0 disables throttling
    weather_cache_ttl_seconds: int = 3600
    weather_attribution: str = "Weather data by Open-Meteo.com"
    weather_user_agent: str = "GeoAgent/0.1 (Phase 5 weather development)"
    weather_noncommercial: bool = True
    # Open-Meteo endpoints (forecast/current + archive + historical-forecast).
    openmeteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    openmeteo_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    openmeteo_historical_forecast_url: str = (
        "https://historical-forecast-api.open-meteo.com/v1/forecast"
    )
    openmeteo_timeout_seconds: float = 30.0
    openmeteo_rate_per_second: float = 0.0  # 0 disables throttling

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
