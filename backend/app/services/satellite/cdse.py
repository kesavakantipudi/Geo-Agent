"""Copernicus Data Space Ecosystem provider (optional satellite source).

Scene discovery uses the public CDSE STAC 1.1 catalogue (``/v1/search``); no
account is required to search. Downloading data assets requires an OAuth2
bearer token issued by the CDSE identity endpoint (password grant with the
public ``cdse-public`` client), so asset retrieval is only possible when
``GEOAGENT_CDSE_USERNAME`` and ``GEOAGENT_CDSE_PASSWORD`` are configured.

The legacy ``catalogue.dataspace.copernicus.eu/stac`` route was deprecated on
17 November 2025 and is intentionally not used.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
from pydantic import BaseModel

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

DEFAULT_COLLECTIONS = ["sentinel-2-l2a", "sentinel-1-grd"]


class _TokenResponse(BaseModel):
    access_token: str
    expires_in: int = 3600


class CDSEProvider(SceneProvider):
    name = "cdse"

    def __init__(self, settings: Settings) -> None:
        self.stac_url = (
            settings.cdse_stac_url or "https://stac.dataspace.copernicus.eu/v1"
        ).rstrip("/")
        self.token_url = (
            settings.cdse_token_url
            or "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
            "protocol/openid-connect/token"
        )
        self.client_id = settings.cdse_client_id or "cdse-public"
        self.username = settings.cdse_username
        self.password = settings.cdse_password
        self.totp = settings.cdse_totp
        self.timeout = settings.satellite_timeout_seconds
        self.user_agent = settings.satellite_user_agent
        self._limiter = RateLimiter(settings.satellite_rate_per_second)
        self._token: str | None = None
        self._token_expiry: datetime | None = None

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
        params: dict[str, Any] = {
            "collections": ",".join(DEFAULT_COLLECTIONS),
            "bbox": ",".join(f"{value:.6f}" for value in bbox),
            "datetime": f"{start.isoformat()}T00:00:00Z/{end.isoformat()}T23:59:59Z",
            "limit": limit,
        }

        self._limiter.wait()
        try:
            with httpx.Client(
                timeout=self.timeout, headers={"User-Agent": self.user_agent}
            ) as client:
                response = client.get(f"{self.stac_url}/search", params=params)
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

        scenes = [self._from_item(item) for item in features]
        return [scene for scene in scenes if _cloud_ok(scene, max_cloud_cover)]

    def download_url(self, asset: dict[str, Any]) -> tuple[str, dict[str, str]]:
        href = (asset or {}).get("href")
        if not href:
            raise SatelliteRetrievalUnsupported("The asset has no download URL.")
        token = self._bearer_token()
        return (str(href), {"Authorization": f"Bearer {token}"})

    def _bearer_token(self) -> str:
        if not self.username or not self.password:
            raise SatelliteRetrievalUnsupported(
                "CDSE asset downloads require GEOAGENT_CDSE_USERNAME and "
                "GEOAGENT_CDSE_PASSWORD to be configured."
            )
        now = datetime.now(UTC)
        if self._token and self._token_expiry and now < self._token_expiry:
            return self._token
        data: dict[str, str] = {
            "client_id": self.client_id,
            "grant_type": "password",
            "username": self.username,
            "password": self.password,
        }
        if self.totp:
            data["totp"] = self.totp
        self._limiter.wait()
        try:
            with httpx.Client(
                timeout=self.timeout, headers={"User-Agent": self.user_agent}
            ) as client:
                response = client.post(self.token_url, data=data)
                response.raise_for_status()
                parsed = _TokenResponse.model_validate(response.json())
        except httpx.TimeoutException as exc:
            raise SatelliteError("The data authentication service timed out.") from exc
        except httpx.RequestError as exc:
            raise SatelliteError("The data authentication service is unavailable.") from exc
        except (httpx.HTTPStatusError, ValueError) as exc:
            raise SatelliteError("The data authentication service rejected the request.") from exc

        self._token = parsed.access_token
        self._token_expiry = now + timedelta(seconds=max(60, parsed.expires_in - 60))
        return self._token

    @staticmethod
    def _from_item(item: dict[str, Any]) -> dict[str, Any]:
        props = item.get("properties") or {}
        acquisition_date = str(props.get("datetime") or "")[:10] or None
        geometry = item.get("geometry")
        return {
            "provider": "cdse",
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


def _cloud_ok(scene: dict[str, Any], max_cloud_cover: float) -> bool:
    cloud = scene.get("cloud_cover")
    if cloud is None:
        return True
    return cloud <= max_cloud_cover
