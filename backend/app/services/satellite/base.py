"""Pluggable satellite scene providers (Phase 4).

A provider turns an AOI bounding box, a date range, and an optional cloud-cover
limit into a list of normalized scene records. Providers are selected via
``GEOAGENT_SATELLITE_ENABLED_PROVIDERS``; the default implementation queries
Microsoft Planetary Computer's STAC API, with the Copernicus Data Space
Ecosystem (CDSE) STAC catalogue available as an optional second source.

Results use a provider-agnostic shape so the search service can deduplicate,
persist, and expose scenes uniformly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any

from app.services.geocoding.base import RateLimiter


def optional_float(value: Any) -> float | None:
    """Best-effort float conversion; returns None for missing/bad values."""
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def optional_bbox(value: Any) -> list[float] | None:
    """Return a [xmin, ymin, xmax, ymax] list or None for unparseable input."""
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        return [float(v) for v in value]
    except (TypeError, ValueError):
        return None


def normalize_assets(assets: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten a STAC ``assets`` map into ``({key, href, media_type, size_bytes})``."""
    result: list[dict[str, Any]] = []
    for key, asset in assets.items():
        if not isinstance(asset, dict) or not asset.get("href"):
            continue
        size_bytes: int | None = None
        try:
            if asset.get("file:size") is not None:
                size_bytes = int(asset["file:size"])
        except (TypeError, ValueError):
            size_bytes = None
        result.append(
            {
                "key": str(key),
                "href": str(asset["href"]),
                "media_type": asset.get("type"),
                "size_bytes": size_bytes,
            }
        )
    return result


#: Normalized scene result keys produced by every provider.
SCENE_KEYS = (
    "provider",
    "scene_id",
    "platform",
    "acquisition_date",
    "cloud_cover",
    "resolution_m",
    "geometry",
    "bbox",
    "assets",
    "metadata",
)


class SatelliteError(Exception):
    """Raised when a provider is unavailable or returns unusable data."""


class SatelliteConfigError(SatelliteError):
    """Raised when the configured provider list is invalid (e.g. unknown name)."""


class SatelliteRetrievalUnsupported(SatelliteError):
    """Raised when a provider cannot produce a download URL for an asset."""


class SceneProvider(ABC):
    """Interface all satellite scene providers must implement."""

    name: str

    @abstractmethod
    def search_scenes(
        self,
        *,
        bbox: tuple[float, float, float, float],
        start: date,
        end: date,
        limit: int,
        max_cloud_cover: float,
    ) -> list[dict[str, Any]]:
        """Return up to ``limit`` scenes covering ``bbox`` within the date range.

        Result keys are the ``SCENE_KEYS``: ``provider``, ``scene_id``,
        ``platform``, ``acquisition_date`` (ISO date or None), ``cloud_cover``,
        ``resolution_m``, ``geometry`` (GeoJSON dict or None), ``bbox``
        ([xmin, ymin, xmax, ymax] or None), ``assets`` (list of
        ``{key, href, media_type, size_bytes}``) and ``metadata`` (dict).
        ``href`` values are unsigned by design: any access token / SAS
        signature is appended by the retrieval layer at download time.
        """

    @abstractmethod
    def download_url(self, asset: dict[str, Any]) -> tuple[str, dict[str, str]]:
        """Return ``(url, headers)`` to download the given asset now.

        Providers that cannot serve asset downloads raise
        :class:`SatelliteRetrievalUnsupported`.
        """


__all__ = [
    "SCENE_KEYS",
    "RateLimiter",
    "SatelliteConfigError",
    "SatelliteError",
    "SatelliteRetrievalUnsupported",
    "SceneProvider",
    "normalize_assets",
    "optional_bbox",
    "optional_float",
]
