"""Geometry validation endpoint (Phase 3).

Lets the frontend validate a drawn or imported GeoJSON geometry before use,
and returns normalized information (type, bbox, centroid, approximate area).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas import geometry as geometry_schemas
from app.services import geometry as geometry_service

router = APIRouter(prefix="/geometries", tags=["geometries"])


@router.post(
    "/validate",
    response_model=geometry_schemas.GeometryValidationResponse,
    summary="Validate and describe a GeoJSON geometry",
)
def validate_geometry_endpoint(
    data: geometry_schemas.GeometryValidationRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return geometry_service.validate_geometry(
        data.geometry, name="geometry", require_area=data.require_area
    )
