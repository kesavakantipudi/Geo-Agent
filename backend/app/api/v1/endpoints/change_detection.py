"""Change-detection endpoints (Phase 6D).

Mirrors the agri/aqua conventions: analysis is anchored to an analysis session
the caller can access, and all data comes from locally retrieved band assets of
**two** temporally ordered scenes. Results that cannot be computed faithfully
are returned as explicit per-type "unavailable" states (HTTP 200) with the
reason preserved. Change analyses are derived on demand, so there are no GET
endpoints — nothing is persisted.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import unavailable
from app.db.session import get_db
from app.models import User
from app.schemas import change_detection as change_schemas
from app.services import change_detection_service
from app.services.change_detection import ChangeDetectionUnavailable

router = APIRouter(prefix="/change-detection", tags=["change-detection"])


@router.post(
    "/analyze",
    response_model=change_schemas.ChangeDetectionResponse,
    summary="Detect vegetation/water change between two scenes over a session AOI",
)
def analyze_endpoint(
    payload: change_schemas.ChangeDetectionRequest,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    try:
        return change_detection_service.analyze(db, user.id, payload)
    except ChangeDetectionUnavailable as exc:
        raise unavailable(str(exc)) from exc
