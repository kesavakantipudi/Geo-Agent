"""Photon (komoot) geocoding provider.

See https://photon.komoot.io/ — a free, key-less geocoder over OpenStreetMap
data. It is throttled by default (``GEOAGENT_GEOCODER_RATE_PER_SECOND``) and
requires only a descriptive User-Agent, which is set from settings.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings
from app.services.geocoding.base import GeocodingError, PlacesProvider, RateLimiter


class PhotonProvider(PlacesProvider):
    name = "photon"

    def __init__(self, settings: Settings) -> None:
        self.url = (settings.geocoder_photon_url or "https://photon.komoot.io/api").rstrip("/")
        self.timeout = settings.geocoder_timeout_seconds
        self.max_results = max(1, min(20, settings.geocoder_max_results))
        self.user_agent = settings.geocoder_user_agent
        self._limiter = RateLimiter(settings.geocoder_rate_per_second)

    def search(
        self,
        query: str,
        limit: int,
        *,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[dict[str, Any]]:
        query = (query or "").strip()
        if not query:
            return []
        limit = max(1, min(limit, self.max_results))

        params: dict[str, Any] = {"q": query, "limit": limit, "lang": "en"}
        if bbox is not None:
            params["bbox"] = ",".join(f"{value:.6f}" for value in bbox)

        self._limiter.wait()
        try:
            with httpx.Client(
                timeout=self.timeout, headers={"User-Agent": self.user_agent}
            ) as client:
                response = client.get(self.url, params=params)
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise GeocodingError("The geocoding service timed out.") from exc
        except httpx.RequestError as exc:
            raise GeocodingError("The geocoding service is unavailable.") from exc
        except (httpx.HTTPStatusError, ValueError) as exc:
            raise GeocodingError("The geocoding service returned an unexpected response.") from exc

        features = payload.get("features") if isinstance(payload, dict) else None
        if not isinstance(features, list):
            raise GeocodingError("The geocoding service returned an unexpected response.")

        results: list[dict[str, Any]] = []
        for feature in features:
            item = self._to_result(feature)
            if item is not None:
                results.append(item)
        return results

    def _to_result(self, feature: dict[str, Any]) -> dict[str, Any] | None:
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("type") != "Point":
            return None
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            return None
        props = feature.get("properties") or {}
        label = self._build_label(props)
        if not label:
            return None
        osm_type = props.get("osm_type") or props.get("osm_key") or "place"
        osm_id = props.get("osm_id")
        place_id = f"{osm_type}:{osm_id}" if osm_id is not None else f"place:{label}"
        return {
            "id": place_id,
            "provider": self.name,
            "label": label,
            "display_name": label,
            "bbox": feature.get("bbox"),
            "center": {"lon": float(coordinates[0]), "lat": float(coordinates[1])},
        }

    @staticmethod
    def _build_label(props: dict[str, Any]) -> str:
        street = props.get("street")
        house_number = props.get("house_number")
        if street:
            first = f"{street} {house_number}".strip()
        else:
            first = props.get("name") or props.get("locality") or ""

        parts = [first]
        for key in ("district", "city", "town", "village", "hamlet", "county", "state", "country"):
            value = props.get(key)
            if value and value not in parts:
                parts.append(str(value))
        return ", ".join(part for part in parts if part).strip()
