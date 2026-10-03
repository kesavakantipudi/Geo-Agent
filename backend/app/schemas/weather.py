"""Weather observation retrieval schemas (Phase 5).

Retrieval is session-scoped exactly like satellite scenes: requests reference an
analysis session (whose AOI and date range drive the provider queries) or an
inline AOI + date range. Responses contain real, normalized observations only;
missing values are ``None`` and are never fabricated as ``0``. Every observation
carries provenance (provider, model, data type, grid cell, timezone), units, and
the provider attribution string.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel

PROVIDER_NAMES = ("openmeteo",)

# (Re)analysis, forecast and seamless "historical forecast" data types
# understood by the weather service. ``current``/``forecast`` use the forecast
# endpoint; ``history``/``archive``/``reanalysis`` use the reanalysis archive;
# ``historical_forecast`` uses the seamless historical-forecast endpoint.
DATA_TYPES = (
    "current",
    "forecast",
    "history",
    "archive",
    "reanalysis",
    "historical_forecast",
)

# Unit groups the provider can convert between.
UNITS = ("metric", "imperial")

# Normalized variable names accepted by the weather service (a provider may
# support only a subset; providers ignore variables they cannot serve).
VARIABLES = (
    "temperature_2m",
    "temperature_2m_max",
    "temperature_2m_min",
    "apparent_temperature",
    "relative_humidity_2m",
    "dewpoint_2m",
    "precipitation",
    "rain",
    "showers",
    "snowfall",
    "weather_code",
    "cloud_cover",
    "pressure_msl",
    "surface_pressure",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "soil_temperature_0cm",
    "soil_moisture_0to10cm",
    "et0_fao_evapotranspiration",
)

DEFAULT_VARIABLES = ("temperature_2m", "relative_humidity_2m")


class WeatherPointSummary(BaseModel):
    """A single stored observation (one variable at one time at one point)."""

    id: int
    provider: str
    model: str | None = None
    data_type: str
    variable: str
    observed_at: datetime
    timezone: str
    value: float | None = None
    units: str | None = None
    units_doc: str | None = None
    latitude: float
    longitude: float
    provenance: dict[str, Any] = {}
    attribution: str


class WeatherSearchRequest(BaseModel):
    # Either an analysis session (recommended) or an inline AOI + dates.
    analysis_session_id: int | None = None
    aoi: dict[str, Any] | None = None
    start_date: date | None = None
    end_date: date | None = None
    # Normalized variables; defaults to provider defaults when omitted.
    variables: list[str] | None = None
    model: str | None = None
    timezone: str = "UTC"
    units: Literal["metric", "imperial"] = "metric"
    data_type: Literal[
        "current",
        "forecast",
        "history",
        "archive",
        "reanalysis",
        "historical_forecast",
    ] = "current"
    # Optional subset of enabled providers.
    providers: list[str] | None = None


class WeatherProviderStatus(BaseModel):
    provider: str
    observations: int = 0
    error: str | None = None


class WeatherSearchResponse(BaseModel):
    observations: list[WeatherPointSummary]
    providers: list[WeatherProviderStatus]
    truncated: bool = False


class WeatherContextRequest(BaseModel):
    """Align already-stored weather observations with a satellite observation.

    ``days_before``/``days_after`` override the configured window (default
    ``GEOAGENT_WEATHER_CONTEXT_WINDOW_DAYS``; capped at ``..._MAX_WINDOW_DAYS``).
    ``variables`` overrides the default context variable set. ``providers`` is
    an optional subset of the configured enabled providers. No provider calls
    are made — this endpoint reads stored data only.
    """

    analysis_session_id: int
    scene_id: int
    days_before: int | None = None
    days_after: int | None = None
    variables: list[str] | None = None
    providers: list[str] | None = None


class WeatherContextVariable(BaseModel):
    name: str
    aggregator: str  # mean | sum | min | max | none
    value: float | None = None  # None = missing, never fabricated as 0
    units: str | None = None
    units_doc: str | None = None
    observation_count: int = 0
    sample_count: int = 0
    expected_count: int = 0
    coverage_pct: float = 0.0
    available: bool = False
    note: str | None = None


class WeatherContextPeriod(BaseModel):
    start: date
    end: date
    days_before: int
    days_after: int


class WeatherContextScene(BaseModel):
    id: int
    scene_id: str
    provider: str
    acquisition_date: date


class WeatherContextUnavailable(BaseModel):
    code: str
    reason: str
    details: list[str] = []


class WeatherContext(BaseModel):
    status: Literal["available", "unavailable"]
    scene: WeatherContextScene
    satellite_observation: date
    period: WeatherContextPeriod | None = None
    variables_requested: list[str] = []
    variables: list[WeatherContextVariable] = []
    observation_count: int = 0
    completeness_pct: float = 0.0
    partial: bool = False
    providers: list[str] = []
    models: list[str] = []
    data_types: list[str] = []
    attribution: str | None = None
    warnings: list[str] = []
    unavailable: WeatherContextUnavailable | None = None
    note: str | None = None  # "Weather context around this observation; no causal claim"


class WeatherContextResponse(BaseModel):
    context: WeatherContext
