"""Agricultural intelligence endpoints (Phase 6A).

Mirrors the satellite/weather conventions: analysis is anchored to an analysis
session the caller can access, and all data comes from locally retrieved band
assets. Results that cannot be computed faithfully are returned as explicit
"unavailable" states (HTTP 200) with the reason preserved; only completed
results are persisted and listable.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import unavailable
from app.db.session import get_db
from app.models import User
from app.schemas import agri as agri_schemas
from app.services import agri_service
from app.services.agri import AgriUnavailable

router = APIRouter(prefix="/agri", tags=["agri"])


@router.post(
    "/analyze",
    response_model=agri_schemas.AgriAnalyzeResponse,
    summary="Compute a spectral-index analysis for a scene over a session AOI",
)
def analyze_endpoint(
    payload: agri_schemas.AgriAnalyzeRequest,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    try:
        return agri_service.analyze(db, user.id, payload)
    except AgriUnavailable as exc:
        raise unavailable(str(exc)) from exc


@router.get(
    "/analyses/{analysis_id}",
    response_model=agri_schemas.AgriAnalysisResult,
    summary="Get a single completed agricultural analysis",
)
def get_analysis_endpoint(
    analysis_id: int,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    return agri_service.get_analysis(db, user.id, analysis_id)


@router.get(
    "/sessions/{session_id}/analyses",
    response_model=list[agri_schemas.AgriAnalysisSummary],
    summary="List completed agricultural analyses for an analysis session",
)
def list_session_analyses_endpoint(
    session_id: int,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    return agri_service.list_analyses_for_session(db, user.id, session_id)
