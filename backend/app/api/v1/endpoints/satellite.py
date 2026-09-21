"""Satellite scene discovery and bounded asset retrieval endpoints (Phase 4).

Scene metadata is public catalogue data, but it is only exposed through
session-scoped access: a user discovers scenes for an analysis session they can
view, and can then inspect/retrieve assets of those scenes. Signed download
URLs are generated server-side and are never returned or persisted.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import unavailable
from app.db.session import get_db
from app.models import User
from app.schemas import satellite as sat_schemas
from app.services import satellite_scene_service
from app.services.satellite import SatelliteError

router = APIRouter(prefix="/satellite", tags=["satellite"])


@router.post(
    "/scenes/search",
    response_model=sat_schemas.SceneSearchResponse,
    summary="Discover satellite scenes for an analysis session AOI and date range",
)
def search_scenes_endpoint(
    payload: sat_schemas.SceneSearchRequest,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    try:
        return satellite_scene_service.search_scenes(db, user.id, payload)
    except SatelliteError as exc:
        raise unavailable(str(exc)) from exc


@router.get(
    "/sessions/{session_id}/scenes",
    response_model=list[sat_schemas.SceneSummary],
    summary="Scenes previously discovered for an analysis session",
)
def list_session_scenes_endpoint(
    session_id: int,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    return satellite_scene_service.list_scenes_for_session(db, user.id, session_id)


@router.get(
    "/scenes/{scene_id}",
    response_model=sat_schemas.SceneSummary,
    summary="Get a single discovered satellite scene",
)
def get_scene_endpoint(
    scene_id: int,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    return satellite_scene_service.get_scene(db, user.id, scene_id)


@router.post(
    "/scenes/{scene_id}/retrievals",
    response_model=list[sat_schemas.RetrievalSummary],
    summary="Download (bound, on demand) selected assets of a scene",
)
def retrieve_assets_endpoint(
    scene_id: int,
    payload: sat_schemas.RetrievalRequest,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    try:
        return satellite_scene_service.retrieve_assets(
            db, user.id, scene_id, payload.asset_keys, payload.analysis_session_id
        )
    except SatelliteError as exc:
        raise unavailable(str(exc)) from exc


@router.get(
    "/scenes/{scene_id}/retrievals",
    response_model=list[sat_schemas.RetrievalSummary],
    summary="Download history for a scene",
)
def list_scene_retrievals_endpoint(
    scene_id: int,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    return satellite_scene_service.list_retrievals(db, user.id, scene_id)


@router.delete(
    "/retrievals/{retrieval_id}",
    status_code=204,
    summary="Delete a retrieval record and its stored file",
)
def delete_retrieval_endpoint(
    retrieval_id: int,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    satellite_scene_service.delete_retrieval(db, user.id, retrieval_id)
    return Response(status_code=204)
