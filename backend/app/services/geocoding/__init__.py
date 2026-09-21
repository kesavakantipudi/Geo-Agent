"""Place geocoding service (Phase 3).

The concrete provider is configurable via ``GEOAGENT_GEOCODER_PROVIDER``
(``photon`` by default, ``none`` to disable). Providers sit behind a small
interface so a search backend can be swapped without touching endpoints.
"""

from __future__ import annotations

from app.services.geocoding.base import PlacesProvider, get_provider

__all__ = ["PlacesProvider", "get_provider", "search_places"]


def search_places(
    query: str, limit: int, *, bbox: tuple[float, float, float, float] | None = None
) -> list[dict]:
    """Geocode a free-text query into a list of place results from the provider."""
    return get_provider().search(query, limit, bbox=bbox)
