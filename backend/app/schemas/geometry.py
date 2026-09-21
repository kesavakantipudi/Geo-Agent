"""Geometry validation schemas (Phase 3).

The frontend sends raw GeoJSON and receives normalized geometry information
(bbox in [lon, lat] order, centroid, and an approximate area).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.services import geometry as geometry_constants


class Centroid(BaseModel):
    lon: float
    lat: float


class GeometryValidationResponse(BaseModel):
    geometry_type: str
    is_valid: bool = True
    point_count: int = 0
    bbox: list[float] | None = None  # [minLon, minLat, maxLon, maxLat]
    centroid: Centroid | None = None
    area_m2_approx: float = 0.0
    srid: int = geometry_constants.SRID
    warnings: list[str] = Field(default_factory=list)


class GeometryValidationRequest(BaseModel):
    geometry: dict[str, Any]  # GeoJSON geometry, Feature, or FeatureCollection
    require_area: bool = False
