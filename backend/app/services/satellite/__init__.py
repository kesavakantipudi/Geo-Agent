"""Satellite scene discovery service (Phase 4).

Scene discovery is provider-agnostic: the concrete sources are configurable via
``GEOAGENT_SATELLITE_ENABLED_PROVIDERS`` (``planetary-computer`` by default,
``cdse`` optional, ``none`` to disable). Providers sit behind a small interface
so a data source can be swapped without touching endpoints or storage.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.services.satellite.base import (
    SatelliteConfigError,
    SatelliteError,
    SatelliteRetrievalUnsupported,
    SceneProvider,
)
from app.services.satellite.cdse import CDSEProvider
from app.services.satellite.planetary_computer import PlanetaryComputerProvider

__all__ = [
    "CDSEProvider",
    "PlanetaryComputerProvider",
    "SatelliteConfigError",
    "SatelliteError",
    "SatelliteRetrievalUnsupported",
    "SceneProvider",
    "get_enabled_provider_names",
    "get_providers",
]


def get_enabled_provider_names() -> list[str]:
    settings = get_settings()
    raw = settings.satellite_enabled_providers or ""
    names = [part.strip().lower() for part in raw.split(",") if part.strip()]
    return [] if not names or "none" in names else names


def get_providers() -> list[SceneProvider]:
    """Instantiate the configured providers (fresh instances per call)."""
    settings = get_settings()
    providers: list[SceneProvider] = []
    for name in get_enabled_provider_names():
        if name == "planetary-computer":
            providers.append(PlanetaryComputerProvider(settings))
        elif name == "cdse":
            providers.append(CDSEProvider(settings))
        else:
            raise SatelliteConfigError(f"Unknown satellite provider '{name}'.")
    return providers
