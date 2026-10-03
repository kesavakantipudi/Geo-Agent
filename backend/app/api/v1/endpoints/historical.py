"""Historical-intelligence endpoints (Phase 6E).

Anchored to an analysis session the caller can access. The session's scenes
are built into a derived-on-demand historical timeline: every observation is
analyzed per requested type (reusing the shared index core), ordered by
acquisition date (oldest → newest), aligned with descriptive weather context,
and consecutive observations are compared into deterministic events (reusing
the Phase 6D change-detection engine). Results are derived on demand, so there
are no GET endpoints — nothing is persisted.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas import historical as historical_schemas
from app.services import historical_service

router = APIRouter(prefix="/historical", tags=["historical"])


@router.post(
    "/analyze",
    response_model=historical_schemas.HistoricalResponse,
    summary="Build a historical timeline over an analysis session's scenes",
)
def analyze_endpoint(
    payload: historical_schemas.HistoricalRequest,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    return historical_service.analyze(db, user.id, payload)
