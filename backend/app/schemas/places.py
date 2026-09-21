"""Place search (geocoding) schemas (Phase 3)."""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.geometry import Centroid


class PlaceResponse(BaseModel):
    id: str
    provider: str
    label: str
    display_name: str = ""
    bbox: list[float] | None = None  # [minLon, minLat, maxLon, maxLat]
    center: Centroid
