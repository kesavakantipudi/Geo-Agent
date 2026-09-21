"""Saved-location CRUD.

Locations are private to their owner; when attached to a workspace the owner
must have access to that workspace (enforced through the workspace service).
Geometry fields (bbox, centroid, area, type) are derived from the stored
EWKT via the shared geometry service.
"""

from __future__ import annotations

from geoalchemy2.functions import ST_AsEWKT
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, not_found
from app.models import SavedLocation
from app.schemas import saved_location as loc_schemas
from app.services import workspace_service
from app.services.geometry import (
    geojson_from_ewkt,
    geometry_info_from_ewkt,
    parse_geometry,
    validate_geometry,
)

_TYPE_FROM_GEOMETRY = {
    "Point": "point",
    "MultiPoint": "point",
    "LineString": "line",
    "MultiLineString": "line",
    "Polygon": "polygon",
    "MultiPolygon": "polygon",
}


def _row_dict(location: SavedLocation, ewkt: str | None) -> dict:
    info = geometry_info_from_ewkt(ewkt)
    return {
        "id": location.id,
        "user_id": location.user_id,
        "workspace_id": location.workspace_id,
        "name": location.name,
        "description": location.description,
        "location_type": location.location_type,
        "center_lat": location.center_lat,
        "center_lon": location.center_lon,
        "geometry": ewkt,
        "geometry_type": info["geometry_type"] if info else None,
        "geometry_geojson": geojson_from_ewkt(ewkt),
        "bbox": info["bbox"] if info else None,
        "centroid": info["centroid"] if info else None,
        "area_m2_approx": info["area_m2_approx"] if info else 0.0,
        "created_at": location.created_at,
        "updated_at": location.updated_at,
    }


def create(db: Session, user_id: int, data: loc_schemas.SavedLocationCreate) -> SavedLocation:
    if data.workspace_id is not None:
        if data.workspace_id <= 0:
            raise bad_request("Invalid workspace_id.")
        workspace_service.require_member(db, data.workspace_id, user_id)

    geometry = None
    location_type = data.location_type
    center = None
    if data.geometry is not None:
        info = validate_geometry(data.geometry, name="location")
        geometry = parse_geometry("location", data.geometry)
        if location_type == "custom":
            location_type = _TYPE_FROM_GEOMETRY.get(info["geometry_type"], "custom")
        center = info["centroid"]

    location = SavedLocation(
        user_id=user_id,
        workspace_id=data.workspace_id,
        name=data.name,
        description=data.description,
        location_type=location_type,
        center_lat=data.center_lat
        if data.center_lat is not None
        else (center["lat"] if center else None),
        center_lon=data.center_lon
        if data.center_lon is not None
        else (center["lon"] if center else None),
        geometry=geometry,
    )
    db.add(location)
    db.flush()
    return location


def list_for_user(db: Session, user_id: int, workspace_id: int | None = None) -> list[dict]:
    query = (
        select(SavedLocation, ST_AsEWKT(SavedLocation.geometry))
        .where(SavedLocation.user_id == user_id)
        .order_by(SavedLocation.created_at)
    )
    if workspace_id is not None:
        query = query.where(SavedLocation.workspace_id == workspace_id)
    rows = db.execute(query).all()
    return [_row_dict(location, ewkt) for location, ewkt in rows]


def get_owned(db: Session, user_id: int, location_id: int) -> dict:
    row = db.execute(
        select(SavedLocation, ST_AsEWKT(SavedLocation.geometry)).where(
            SavedLocation.id == location_id,
            SavedLocation.user_id == user_id,
        )
    ).one_or_none()
    if row is None:
        raise not_found("Saved location not found.", code="location_not_found")
    return _row_dict(row[0], row[1])


def update(
    db: Session, user_id: int, location_id: int, data: loc_schemas.SavedLocationUpdate
) -> dict:
    location = db.execute(
        select(SavedLocation).where(
            SavedLocation.id == location_id, SavedLocation.user_id == user_id
        )
    ).scalar_one_or_none()
    if location is None:
        raise not_found("Saved location not found.", code="location_not_found")
    if data.name is not None:
        location.name = data.name
    if data.description is not None:
        location.description = data.description
    db.flush()
    return get_owned(db, user_id, location_id)


def delete(db: Session, user_id: int, location_id: int) -> None:
    location = db.execute(
        select(SavedLocation).where(
            SavedLocation.id == location_id, SavedLocation.user_id == user_id
        )
    ).scalar_one_or_none()
    if location is None:
        raise not_found("Saved location not found.", code="location_not_found")
    db.delete(location)
    db.flush()
