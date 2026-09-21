"""Microsoft Planetary Computer provider (default satellite source).

Scene discovery uses the key-less STAC API (``/search``, CQL2-JSON), so no
account or subscription key is required. Data assets live on Azure Blob
storage; their ``href`` values are unsigned by default, which is what we
persist. Downloading an asset signs the href on demand via the Data
Authentication API (``GET /sas/v1/sign?href=...``).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from app.core.config import Settings
from app.services.geocoding.base import RateLimiter
from app.services.satellite.base import (
    SatelliteError,
    SatelliteRetrievalUnsupported,
    SceneProvider,
    normalize_assets,
    optional_bbox,
    optional_float,
)

# Sentinel-2 L2A (optical), Sentinel-1 RTC (radar) and Landsat C2 L2 (USGS via
# Planetary Computer) cover the analysis-session workflows of the roadmap.
DEFAULT_COLLECTIONS = ["sentinel-2-l2a", "sentinel-1-rtc", "landsat-c2-l2"]
MAX_CLOUD_VALUE = 100.0


class PlanetaryComputerProvider(SceneProvider):
    name = "planetary-computer"

    def __init__(self, settings: Settings) -> None:
        self.stac_url = (
            settings.planetary_computer_stac_url
            or "https://planetarycomputer.microsoft.com/api/stac/v1"
        ).rstrip("/")
        self.sas_url = (
            settings.planetary_computer_sas_url
            or "https://planetarycomputer.microsoft.com/api/sas/v1"
        ).rstrip("/")
        self.timeout = settings.satellite_timeout_seconds
        self.user_agent = settings.satellite_user_agent
        self._limiter = RateLimiter(settings.satellite_rate_per_second)

    def search_scenes(
        self,
        *,
        bbox: tuple[float, float, float, float],
        start: date,
        end: date,
        limit: int,
        max_cloud_cover: float,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        payload: dict[str, Any] = {
            "collections": list(DEFAULT_COLLECTIONS),
            "bbox": [float(value) for value in bbox],
            "datetime": f"{start.isoformat()}T00:00:00Z/{end.isoformat()}T23:59:59Z",
            "limit": limit,
        }
        if max_cloud_cover < MAX_CLOUD_VALUE:
            payload["filter-lang"] = "cql2-json"
            payload["filter"] = {
                "op": "<=",
                "args": [{"property": "eo:cloud_cover"}, float(max_cloud_cover)],
            }

        self._limiter.wait()
        try:
            with httpx.Client(
                timeout=self.timeout, headers={"User-Agent": self.user_agent}
            ) as client:
                response = client.post(f"{self.stac_url}/search", json=payload)
                response.raise_for_status()
                features = response.json().get("features")
        except httpx.TimeoutException as exc:
            raise SatelliteError("The satellite data service timed out.") from exc
        except httpx.RequestError as exc:
            raise SatelliteError("The satellite data service is unavailable.") from exc
        except (httpx.HTTPStatusError, ValueError) as exc:
            raise SatelliteError(
                "The satellite data service returned an unexpected response."
            ) from exc

        if not isinstance(features, list):
            raise SatelliteError("The satellite data service returned an unexpected response.")
        return [self._from_item(item) for item in features]

    def download_url(self, asset: dict[str, Any]) -> tuple[str, dict[str, str]]:
        href = (asset or {}).get("href")
        if not href:
            raise SatelliteRetrievalUnsupported("The asset has no download URL.")
        self._limiter.wait()
        try:
            with httpx.Client(
                timeout=self.timeout, headers={"User-Agent": self.user_agent}
            ) as client:
                response = client.get(f"{self.sas_url}/sign", params={"href": href})
                response.raise_for_status()
                signed = response.json().get("href")
        except httpx.TimeoutException as exc:
            raise SatelliteError("The data signing service timed out.") from exc
        except httpx.RequestError as exc:
            raise SatelliteError("The data signing service is unavailable.") from exc
        except (httpx.HTTPStatusError, ValueError) as exc:
            raise SatelliteError(
                "The data signing service returned an unexpected response."
            ) from exc
        if not signed:
            raise SatelliteError("The data signing service returned an unexpected response.")
        return (signed, {})

    @staticmethod
    def _from_item(item: dict[str, Any]) -> dict[str, Any]:
        props = item.get("properties") or {}
        acquisition_date = str(props.get("datetime") or "")[:10] or None
        geometry = item.get("geometry")
        return {
            "provider": "planetary-computer",
            "scene_id": str(item.get("id") or ""),
            "platform": props.get("platform"),
            "acquisition_date": acquisition_date,
            "cloud_cover": optional_float(props.get("eo:cloud_cover")),
            "resolution_m": optional_float(props.get("gsd")),
            "geometry": geometry if isinstance(geometry, dict) else None,
            "bbox": optional_bbox(item.get("bbox")),
            "assets": normalize_assets(item.get("assets") or {}),
            "metadata": {
                "constellation": props.get("constellation"),
                "instrument": props.get("instrument"),
                "processing_level": props.get("processing:level"),
                "title": props.get("title") or item.get("id"),
            },
        }
