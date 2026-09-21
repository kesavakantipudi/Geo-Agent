"""Saved-location endpoints (foundation for Phase 3 location intelligence)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas import saved_location as loc_schemas
from app.services import saved_location_service

router = APIRouter(prefix="/saved-locations", tags=["saved-locations"])


@router.get(
    "", response_model=list[loc_schemas.SavedLocationResponse], summary="List my saved locations"
)
def list_locations(
    workspace_id: Annotated[int | None, Query()] = None,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    results = saved_location_service.list_for_user(db, user.id, workspace_id)
    return [loc_schemas.SavedLocationResponse(**item) for item in results]


@router.post(
    "",
    response_model=loc_schemas.SavedLocationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a location",
)
def create_location(
    data: loc_schemas.SavedLocationCreate,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    location = saved_location_service.create(db, user.id, data)
    db.commit()
    return loc_schemas.SavedLocationResponse(
        **saved_location_service.get_owned(db, user.id, location.id)
    )


@router.get(
    "/{location_id}",
    response_model=loc_schemas.SavedLocationResponse,
    summary="Get a saved location",
)
def get_location(
    location_id: int,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    return loc_schemas.SavedLocationResponse(
        **saved_location_service.get_owned(db, user.id, location_id)
    )


@router.patch(
    "/{location_id}",
    response_model=loc_schemas.SavedLocationResponse,
    summary="Update a saved location",
)
def update_location(
    location_id: int,
    data: loc_schemas.SavedLocationUpdate,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    result = saved_location_service.update(db, user.id, location_id, data)
    db.commit()
    return loc_schemas.SavedLocationResponse(**result)


@router.delete(
    "/{location_id}",
    response_model=loc_schemas.SavedLocationResponse,
    summary="Delete a saved location",
)
def delete_location(
    location_id: int,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    result = saved_location_service.get_owned(db, user.id, location_id)
    saved_location_service.delete(db, user.id, location_id)
    db.commit()
    return loc_schemas.SavedLocationResponse(**result)
