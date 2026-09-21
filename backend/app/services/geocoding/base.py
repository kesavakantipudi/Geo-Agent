"""Pluggable place-geocoding providers.

A provider turns a free-text query (optionally scoped to a bounding box) into a
list of place results with a stable identifier, a display label, a bbox
([minLon, minLat, maxLon, maxLat]) and a center point. Providers are selected
via ``GEOAGENT_GEOCODER_PROVIDER``; the default implementation queries Photon.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any

from app.core.config import get_settings


class GeocodingError(Exception):
    """Raised when a provider is unavailable or returns unusable data."""


class PlacesProvider(ABC):
    """Interface all geocoding providers must implement."""

    name: str

    @abstractmethod
    def search(
        self,
        query: str,
        limit: int,
        *,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[dict[str, Any]]:
        """Return up to ``limit`` place results for ``query``.

        Result keys: ``id``, ``provider``, ``label``, ``display_name``,
        ``bbox`` (list or None) and ``center`` ({'lon', 'lat'}).
        """


class RateLimiter:
    """Simple in-process throttle: at most one request every ``1/rate`` s.

    The lock is held while sleeping so concurrency is bounded regardless of the
    number of worker threads. This is a best-effort politeness guard for
    key-less public services (Photon/Nominatim), not a production rate limit.
    """

    def __init__(self, rate_per_second: float) -> None:
        self.interval = 1.0 / rate_per_second if rate_per_second > 0 else 0.0
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        if self.interval <= 0:
            return
        with self._lock:
            elapsed = time.monotonic() - self._last
            if elapsed < self.interval:
                time.sleep(self.interval - elapsed)
            self._last = time.monotonic()


class DisabledProvider(PlacesProvider):
    """Returns no results; used when geocoding is disabled (provider "none")."""

    name = "none"

    def search(self, query, limit=8, *, bbox=None):
        return []


@lru_cache(maxsize=1)
def get_provider() -> PlacesProvider:
    """Build (and cache) the configured provider instance."""
    from app.services.geocoding.photon import PhotonProvider

    settings = get_settings()
    provider_name = (settings.geocoder_provider or "photon").strip().lower()
    if provider_name in ("none", "disabled", "off"):
        return DisabledProvider()
    if provider_name == "photon":
        return PhotonProvider(settings)
    raise GeocodingError(f"Unknown geocoder provider '{provider_name}'.")
