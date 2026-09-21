"""Saved-location CRUD. Locations are private to their owner unless shared via a workspace."""

from __future__ import annotations

from geoalchemy2.functions import ST_AsEWKT
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, not_found
from app.models import SavedLocation
from app.schemas import saved_location as loc_schemas
from app.services.geometry import parse_geometry


def _row_dict(location: SavedLocation, ewkt: str | None) -> dict:
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
        "created_at": location.created_at,
        "updated_at": location.updated_at,
    }


def create(db: Session, user_id: int, data: loc_schemas.SavedLocationCreate) -> SavedLocation:
    if data.workspace_id is not None and data.workspace_id <= 0:
        raise bad_request("Invalid workspace_id.")
    geometry = None
    if data.geometry is not None:
        geometry = parse_geometry("location", data.geometry)
    location = SavedLocation(
        user_id=user_id,
        workspace_id=data.workspace_id,
        name=data.name,
        description=data.description,
        location_type=data.location_type,
        center_lat=data.center_lat,
        center_lon=data.center_lon,
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
