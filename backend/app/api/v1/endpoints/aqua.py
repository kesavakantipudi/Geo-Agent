"""Water intelligence endpoints (Phase 6B).

Mirrors the satellite/weather/agri conventions: analysis is anchored to an
analysis session the caller can access, and all data comes from locally
retrieved band assets. Results that cannot be computed faithfully are returned
as explicit "unavailable" states (HTTP 200) with the reason preserved. NDWI
analyses are derived on demand, so there are no GET endpoints — nothing is
persisted.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import unavailable
from app.db.session import get_db
from app.models import User
from app.schemas import aqua as aqua_schemas
from app.services import aqua_service
from app.services.aqua import AquaUnavailable

router = APIRouter(prefix="/aqua", tags=["aqua"])


@router.post(
    "/analyze",
    response_model=aqua_schemas.AquaAnalyzeResponse,
    summary="Compute an NDWI water analysis for a scene over a session AOI",
)
def analyze_endpoint(
    payload: aqua_schemas.AquaAnalyzeRequest,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    try:
        return aqua_service.analyze(db, user.id, payload)
    except AquaUnavailable as exc:
        raise unavailable(str(exc)) from exc
