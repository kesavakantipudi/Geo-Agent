"""Weather observation retrieval (Phase 5).

Phase 5 adds weather observations for an analysis session's AOI and date
range. Mirroring the satellite layer, weather is provider-agnostic: concrete
sources are configured via ``GEOAGENT_WEATHER_ENABLED_PROVIDERS`` and each
provider sits behind the :class:`WeatherProvider` interface so a source can be
swapped without touching endpoints or persistence.

Phase 5 rules:

- Observations are *real*: every value comes from the provider's recorded
  response. Nothing is invented, extrapolated, or "filled in to look real".
- Normalized units: responses carry ``units`` (a per-variable dict) and
  ``units_doc`` so the frontend always renders the correct unit next to the
  value.
- Timestamps: every observation has an exact ``observed_at`` (ISO-8601 with
  offset) plus the ``timezone``/``tz_source`` the provider metadata described.
  The frontend renders timestamps in that timezone, never the browser's local
  time.
- Provenance: every observation keeps its provenance dict (source URL, model,
  grid cell, aggregation, attribution) so results can always be attributed
  ("Weather data by Open-Meteo.com") and verified.
- Missing values stay missing: when a provider reports no value (e.g. no
  archive coverage for the requested period/model/variable), the normalized
  comparison value is ``None`` — never ``0`` (which would fabricate a
  measurement) and never a silently-substituted archive value.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.services.geocoding.base import RateLimiter


def optional_float(value: Any) -> float | None:
    """Best-effort float conversion; returns None (not 0) for missing/bad values."""
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class WeatherError(Exception):
    """Base error for weather retrieval failures."""


class WeatherConfigError(WeatherError):
    """Raised when the provider configuration is invalid (e.g. unknown name)."""


class WeatherRetrievalUnsupported(WeatherError):
    """Raised when a provider cannot serve the requested period/variable/model."""


class WeatherProvider(ABC):
    """Interface all weather providers must implement."""

    name: str

    @abstractmethod
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
        """Return normalized observations for the AOI ``bbox``.

        ``bbox`` is ``(min_lat, min_lon, max_lat, max_lon)`` (the AOI bounding
        box in latitude/longitude order). Each item is a dict with keys:
        ``observed_at`` (ISO-8601 in the provider timezone), ``timezone``,
        ``data_type``, ``latitude``, ``longitude``, ``model``, ``variables``
        (variable → value-or-None), ``units`` (per-variable dict), ``units_doc``,
        ``provenance``, ``attribution``, ``user_agent`` and ``noncommercial``.
        Missing values are ``None``, never ``0``.
        """
        raise NotImplementedError


__all__ = [
    "RateLimiter",
    "WeatherConfigError",
    "WeatherError",
    "WeatherProvider",
    "WeatherRetrievalUnsupported",
    "optional_float",
]
