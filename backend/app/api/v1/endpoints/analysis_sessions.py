"""Analysis-session endpoints (Phase 3: AOI, date range, agent selection).

Sessions are created as ``draft``; execution belongs to a later phase.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas import analysis_session as ses_schemas
from app.services import analysis_session_service

router = APIRouter(prefix="/analysis-sessions", tags=["analysis-sessions"])


@router.get(
    "",
    response_model=list[ses_schemas.AnalysisSessionResponse],
    summary="List analysis sessions I can access",
)
def list_sessions(
    workspace_id: Annotated[int | None, Query()] = None,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    results = analysis_session_service.list_for_user(db, user.id, workspace_id)
    return [ses_schemas.AnalysisSessionResponse(**item) for item in results]


@router.post(
    "",
    response_model=ses_schemas.AnalysisSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a draft analysis session",
)
def create_session(
    data: ses_schemas.AnalysisSessionCreate,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    result = analysis_session_service.create(db, user.id, data)
    db.commit()
    return ses_schemas.AnalysisSessionResponse(**result)


@router.get(
    "/{session_id}",
    response_model=ses_schemas.AnalysisSessionResponse,
    summary="Get an analysis session",
)
def get_session(
    session_id: int,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    return ses_schemas.AnalysisSessionResponse(
        **analysis_session_service.get(db, user.id, session_id)
    )


@router.patch(
    "/{session_id}",
    response_model=ses_schemas.AnalysisSessionResponse,
    summary="Update a draft analysis session (owner only)",
)
def update_session(
    session_id: int,
    data: ses_schemas.AnalysisSessionUpdate,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    result = analysis_session_service.update(db, user.id, session_id, data)
    db.commit()
    return ses_schemas.AnalysisSessionResponse(**result)


@router.delete(
    "/{session_id}",
    response_model=ses_schemas.AnalysisSessionResponse,
    summary="Delete an analysis session (owner only)",
)
def delete_session(
    session_id: int,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    result = analysis_session_service.delete(db, user.id, session_id)
    db.commit()
    return ses_schemas.AnalysisSessionResponse(**result)
