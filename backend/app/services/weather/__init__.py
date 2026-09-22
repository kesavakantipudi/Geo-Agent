"""Weather observation retrieval registry (Phase 5).

Mirrors the satellite registry: concrete providers are configured via
``GEOAGENT_WEATHER_ENABLED_PROVIDERS`` (comma-separated; ``none`` or an empty
value disables weather retrieval entirely) and each instantiation happens here
so endpoints/persistence never decide which source backs a result.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.services.weather.base import (
    WeatherConfigError,
    WeatherError,
    WeatherProvider,
    WeatherRetrievalUnsupported,
)
from app.services.weather.openmeteo import OpenMeteoProvider

#: Possible provider names, mirrored from the enabled-providers contract.
_PROVIDER_NAMES: frozenset[str] = frozenset({"openmeteo"})


def get_enabled_weather_provider_names() -> list[str]:
    """Return the provider names enabled in settings (lower-cased, deduped).

    Empty/``none`` → ``[]`` (weather retrieval disabled).
    """
    settings = get_settings()
    raw = getattr(settings, "weather_enabled_providers", "") or ""
    names = [name.strip().lower() for name in raw.split(",") if name.strip()]
    if not names or "none" in names:
        return []
    seen: list[str] = []
    for name in names:
        if name not in _PROVIDER_NAMES:
            raise WeatherConfigError(f"unknown weather provider '{name}'")
        if name not in seen:
            seen.append(name)
    return seen


def get_weather_providers() -> list[WeatherProvider]:
    """Instantiate enabled weather providers (fresh instances per call)."""
    settings = get_settings()
    providers: list[WeatherProvider] = []
    for name in get_enabled_weather_provider_names():
        if name == "openmeteo":
            providers.append(OpenMeteoProvider(settings))
        else:  # pragma: no cover - guarded by get_enabled_weather_provider_names
            raise WeatherConfigError(f"unknown weather provider '{name}'")
    return providers


__all__ = [
    "OpenMeteoProvider",
    "WeatherConfigError",
    "WeatherError",
    "WeatherProvider",
    "WeatherRetrievalUnsupported",
    "get_enabled_weather_provider_names",
    "get_weather_providers",
]
