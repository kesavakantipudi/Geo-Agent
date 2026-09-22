"""Weather observation retrieval endpoints (Phase 5).

Mirrors the satellite endpoints: session-scoped discovery plus read access to
previously persisted observations. No API keys, no fabrication — every value
returned is a real provider response; missing values are ``None``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import unavailable
from app.db.session import get_db
from app.models import User
from app.schemas import weather as weather_schemas
from app.services import weather_service
from app.services.weather import WeatherError

router = APIRouter(prefix="/weather", tags=["weather"])


@router.post(
    "/search",
    response_model=weather_schemas.WeatherSearchResponse,
    summary="Retrieve weather observations for an analysis session AOI and date range",
)
def search_weather_endpoint(
    payload: weather_schemas.WeatherSearchRequest,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    try:
        return weather_service.fetch_weather_endpoint(db, user.id, payload)
    except WeatherError as exc:
        raise unavailable(str(exc)) from exc


@router.get(
    "/sessions/{session_id}/observations",
    response_model=list[weather_schemas.WeatherPointSummary],
    summary="Observations previously retrieved for an analysis session",
)
def list_session_observations_endpoint(
    session_id: int,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    return weather_service.list_observations_for_session(db, user.id, session_id)


@router.get(
    "/observations/{observation_id}",
    response_model=weather_schemas.WeatherPointSummary,
    summary="Get a single stored weather observation",
)
def get_observation_endpoint(
    observation_id: int,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    return weather_service.get_observation(db, user.id, observation_id)
