"""User profile endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas import user as user_schemas
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=user_schemas.UserProfileResponse, summary="Current user profile")
def get_me(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return user_service.get_profile(db, user)


@router.patch(
    "/me", response_model=user_schemas.UserProfileResponse, summary="Update current user profile"
)
def update_me(
    data: user_schemas.UserUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    updated = user_service.update_profile(db, user, data)
    db.commit()
    return user_service.get_profile(db, updated)
