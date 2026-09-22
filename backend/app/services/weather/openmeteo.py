"""Open-Meteo provider (Phase 5).

Open-Meteo is a **non-commercial** service: the free tier allows *fewer than
10,000 calls per day*, requires no API key, and all data must be attributed —
"Weather data by Open-Meteo.com". Because that tier is non-commercial, every
normalized observation records ``noncommercial=True`` and the ``attribution``
string so attribution is always visible in the UI and the operator can confirm
compliance.

Endpoints (config-driven):

- ``openmeteo_forecast_url`` — current conditions + up to 16-day forecast, with
  ``past_days`` (observed values merged seamlessly with the forecast). Serves
  ``current`` and ``forecast`` data types.
- ``openmeteo_archive_url`` — the reanalysis archive: ERA5 since 1940,
  ERA5-Land since 1950, matched to the nearest ERA5 grid cell. Serves
  ``history`` / ``archive`` / ``reanalysis`` **only** — never current/forecast
  (that would fabricate). Anything without archive coverage normalizes to
  ``None``, never ``0``.
- ``openmeteo_historical_forecast_url`` — the seamless "historical forecast"
  from 2022 plus the previous model run for forecast-lag/skill evaluation.
  Serves ``historical_forecast``.

Normalization rules (mirroring the satellite layer):

- **Real values only**: every value is the provider's recorded value. Nothing
  invented, extrapolated, or "filled in to look real".
- **Missing stays missing**: provider-reported absence → ``None``, never ``0``
  (which would fabricate a measurement) and never a silently-substituted
  archive value.
- **Units + timestamps + timezone + provenance + attribution** are always
  attached so the frontend renders the correct unit, exact timestamp
  (ISO-8601 with offset) in the provider timezone, and provenance/attribution
  — "Weather data by Open-Meteo.com".
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.services.weather.base import (
    RateLimiter,
    WeatherError,
    WeatherProvider,
    WeatherRetrievalUnsupported,
    optional_float,
)

#: Normalized variable names → Open-Meteo query variable.
OPENMETEO_VARIABLES: dict[str, str] = {
    "temperature_2m": "temperature_2m",
    "temperature_2m_max": "temperature_2m_max",
    "temperature_2m_min": "temperature_2m_min",
    "apparent_temperature": "apparent_temperature",
    "relative_humidity_2m": "relative_humidity_2m",
    "dewpoint_2m": "dewpoint_2m",
    "precipitation": "precipitation",
    "rain": "rain",
    "showers": "showers",
    "snowfall": "snowfall",
    "weather_code": "weather_code",
    "cloud_cover": "cloud_cover",
    "pressure_msl": "pressure_msl",
    "surface_pressure": "surface_pressure",
    "wind_speed_10m": "wind_speed_10m",
    "wind_direction_10m": "wind_direction_10m",
    "wind_gusts_10m": "wind_gusts_10m",
    "soil_temperature_0cm": "soil_temperature_0cm",
    "soil_moisture_0to10cm": "soil_moisture_0to10cm",
    "et0_fao_evapotranspiration": "et0_fao_evapotranspiration",
}

#: Data types served by each endpoint kind.
SUPPORTED_DATA_TYPES: dict[str, str] = {
    "current": "forecast",
    "forecast": "forecast",
    "history": "archive",
    "archive": "archive",
    "reanalysis": "archive",
    "historical_forecast": "historical_forecast",
}

#: The archive endpoint serves history/archive/reanalysis **only**.
ARCHIVE_DATA_TYPES: frozenset[str] = frozenset({"history", "archive", "reanalysis"})
#: The historical-forecast endpoint serves historical_forecast (seamless 2022+).
HISTORICAL_FORECAST_DATA_TYPES: frozenset[str] = frozenset({"historical_forecast"})


class OpenMeteoProvider(WeatherProvider):
    """Weather provider backed by the free Open-Meteo HTTP API (no key)."""

    name = "openmeteo"

    def __init__(self, settings=None) -> None:
        settings = settings or get_settings()
        base = getattr(settings, "openmeteo_base_url", "") or ("https://api.open-meteo.com/v1")
        base = base.rstrip("/")
        self._urls = {
            "forecast": (getattr(settings, "openmeteo_forecast_url", "") or f"{base}/forecast"),
            "archive": (getattr(settings, "openmeteo_archive_url", "") or f"{base}/archive"),
            "historical_forecast": (
                getattr(settings, "openmeteo_historical_forecast_url", "")
                or "https://historical-forecast-api.open-meteo.com/v1/forecast"
            ),
        }
        self.timeout = getattr(settings, "openmeteo_timeout_seconds", 30.0)
        self.user_agent = getattr(
            settings, "weather_user_agent", "GeoAgent/0.1 (Phase 5 weather development)"
        )
        self.attribution = getattr(
            settings, "weather_attribution", "Weather data by Open-Meteo.com"
        )
        self.noncommercial = bool(getattr(settings, "weather_noncommercial", True))
        self._limiter = RateLimiter(getattr(settings, "openmeteo_rate_per_second", 0.0))
        self._client = httpx.Client(
            timeout=self.timeout,
            headers={"User-Agent": self.user_agent},
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    # -- provider contract ----------------------------------------------------
    def fetch_weather(
        self,
        *,
        bbox: tuple[float, float, float, float],
        start: str,
        end: str,
        variables: list[str],
        model: str | None,
        timezone: str,
        units: str,
        data_type: str,  # current | forecast | history | archive | reanalysis
    ) -> list[dict[str, Any]]:
        """Fetch + normalize Open-Meteo observations for ``bbox`` within the range.

        ``data_type`` selects the endpoint: current/forecast → the forecast
        URL; history/archive/reanalysis → the archive URL; historical_forecast
        → the historical-forecast URL. Archive responses are the ERA5/ERA5-Land
        reanalysis matched to the nearest grid cell and are normalized using
        the model grid metadata (see ``_grid_meta``).

        Rule: every value is real (recorded), missing values normalize to
        ``None`` (never ``0``), and each observation keeps its
        units/timezone/timestamps/provenance/attribution.
        """
        min_lat, min_lon, max_lat, max_lon = bbox
        lat = (min_lat + max_lat) / 2.0
        lon = (min_lon + max_lon) / 2.0

        kind = SUPPORTED_DATA_TYPES.get(data_type)
        if kind is None:
            raise WeatherRetrievalUnsupported(f"openmeteo: unsupported data type '{data_type}'")
        url = self._urls[kind]
        if kind in ARCHIVE_DATA_TYPES or kind in HISTORICAL_FORECAST_DATA_TYPES:
            url = self._urls[kind]

        query_vars = [OPENMETEO_VARIABLES[v] for v in variables if v in OPENMETEO_VARIABLES]
        if not query_vars:
            raise WeatherRetrievalUnsupported("openmeteo: no supported variables requested")

        params: dict[str, Any] = {
            "latitude": lat,
            "longitude": lon,
            "timezone": timezone,
        }
        if model:
            params["model"] = model
        if kind != "forecast":
            params["start_date"] = start
            params["end_date"] = end
        params["hourly"] = ",".join(query_vars)
        if units == "imperial":
            params["temperature_unit"] = "fahrenheit"
            params["wind_speed_unit"] = "mph"
            params["precipitation_unit"] = "inch"

        self._limiter.wait()
        try:
            resp = self._client.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise WeatherError("openmeteo: rate limited (HTTP 429)") from exc
            raise WeatherError(
                f"openmeteo: HTTP {exc.response.status_code} for "
                f"{exc.request.url}: {exc.response.text[:200]}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise WeatherError("openmeteo: timeout fetching") from exc
        except httpx.HTTPError as exc:
            raise WeatherError(f"openmeteo: request failed: {exc}") from exc

        return self._normalize(
            payload,
            lat=lat,
            lon=lon,
            timezone=timezone,
            variables=variables,
            units=units,
            data_type=data_type,
            model=model,
        )

    # -- normalization --------------------------------------------------------
    def _grid_meta(self, lat: float, lon: float) -> dict[str, Any]:
        """Nearest ERA5 grid cell metadata for provenance."""
        return {
            "grid_cell": {
                "lat": round(lat * 4.0) / 4.0,
                "lon": round(lon * 4.0) / 4.0,
            },
            "grid_step": {"lat": 0.25, "lon": 0.25},
            "basis": "ERA5/ERA5-Land ~0.25deg grid (Open-Meteo archive)",
        }

    def _normalize(
        self,
        payload: dict[str, Any],
        *,
        lat: float,
        lon: float,
        timezone: str,
        variables: list[str],
        units: str,
        data_type: str,
        model: str | None,
    ) -> list[dict[str, Any]]:
        hourly = payload.get("hourly") or {}
        times = hourly.get("time") or []
        hourly_units = payload.get("hourly_units") or {}
        obs: list[dict[str, Any]] = []

        # Only persist the requested variables, never extras the provider
        # happens to return (the client asked for a precise subset).
        requested_query = {
            OPENMETEO_VARIABLES[var] for var in variables if var in OPENMETEO_VARIABLES
        }

        for idx, raw_time in enumerate(times):
            variables_norm: dict[str, float | None] = {}
            for var in hourly:
                if var not in requested_query:
                    continue
                values = hourly.get(var) or []
                variables_norm[var] = optional_float(values[idx] if idx < len(values) else None)
            obs.append(
                {
                    "observed_at": raw_time,  # ISO-8601, provider timezone
                    "timezone": payload.get("timezone") or timezone,
                    "data_type": data_type,
                    "latitude": lat,
                    "longitude": lon,
                    "model": payload.get("model") or model,
                    "variables": variables_norm,
                    "units": dict(hourly_units),
                    "units_doc": "Open-Meteo hourly units (see response hourly_units field)",
                    "provenance": {
                        "provider": self.name,
                        "source_url": next(iter(self._urls.values()), ""),
                        "model": payload.get("model") or model,
                        "grid_cell": self._grid_meta(lat, lon),
                        "aggregation": "point (nearest ERA5 grid cell)",
                        "attribution": self.attribution,
                    },
                    "attribution": self.attribution,
                    "user_agent": self.user_agent,
                    "noncommercial": self.noncommercial,
                }
            )
        return obs


__all__ = ["OPENMETEO_VARIABLES", "OpenMeteoProvider", "SUPPORTED_DATA_TYPES"]
