"""Place search (geocoding) endpoint (Phase 3)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import bad_request, unavailable
from app.db.session import get_db
from app.models import User
from app.schemas import places as places_schemas
from app.services.geocoding import search_places
from app.services.geocoding.base import GeocodingError
from app.services.geometry import LAT_MAX, LAT_MIN, LON_MAX, LON_MIN

router = APIRouter(prefix="/places", tags=["places"])


def _bbox_from_string(value: str | None) -> tuple[float, float, float, float] | None:
    """Parse an optional ``minLon,minLat,maxLon,maxLat`` query parameter."""
    if not value:
        return None
    parts = value.split(",")
    if len(parts) != 4:
        raise bad_request(
            "The bbox parameter must be 'minLon,minLat,maxLon,maxLat'.",
            code="invalid_bbox",
        )
    try:
        min_lon, min_lat, max_lon, max_lat = (float(part) for part in parts)
    except ValueError as exc:
        raise bad_request("The bbox parameter must contain numbers.", code="invalid_bbox") from exc
    if not (LON_MIN <= min_lon <= LON_MAX and LON_MIN <= max_lon <= LON_MAX):
        raise bad_request("The bbox longitudes are out of range.", code="invalid_bbox")
    if not (LAT_MIN <= min_lat <= LAT_MAX and LAT_MIN <= max_lat <= LAT_MAX):
        raise bad_request("The bbox latitudes are out of range.", code="invalid_bbox")
    if min_lon > max_lon or min_lat > max_lat:
        raise bad_request(
            "The bbox min values must not exceed the max values.", code="invalid_bbox"
        )
    return (min_lon, min_lat, max_lon, max_lat)


@router.get(
    "/search",
    response_model=list[places_schemas.PlaceResponse],
    summary="Search places (geocoding provider, configurable via env)",
)
def search_place_endpoint(
    q: Annotated[str, Query(min_length=2, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
    bbox: Annotated[str | None, Query()] = None,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    try:
        results = search_places(q, limit, bbox=_bbox_from_string(bbox))
    except GeocodingError as exc:
        raise unavailable(str(exc)) from exc
    return [places_schemas.PlaceResponse(**item) for item in results]
