"""Saved-location schemas.

Geometry is accepted as EWKT (e.g. ``SRID=4326;POINT(81.83 17.0)`` or
``SRID=4326;POLYGON((...))``) or as a GeoJSON geometry object (Point,
LineString, Polygon for Phase 2). SRID is pinned to 4326.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SavedLocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    workspace_id: int | None = None
    location_type: Literal["point", "polygon", "custom"] = "custom"
    center_lat: float | None = None
    center_lon: float | None = None
    geometry: str | dict[str, Any] | None = None  # EWKT string or GeoJSON geometry


class SavedLocationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class SavedLocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    workspace_id: int | None = None
    name: str
    description: str | None = None
    location_type: str
    center_lat: float | None = None
    center_lon: float | None = None
    geometry: str | None = None  # EWKT text from the database
    geometry_type: str | None = None
    geometry_geojson: dict[str, Any] | None = None  # same geometry in GeoJSON
    bbox: list[float] | None = None  # [minLon, minLat, maxLon, maxLat]
    centroid: dict[str, float] | None = None  # {"lon": ..., "lat": ...}
    area_m2_approx: float = 0.0
    created_at: datetime
    updated_at: datetime
