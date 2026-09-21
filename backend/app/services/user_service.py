"""User profile operations."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core import security
from app.core.exceptions import bad_request, unauthorized
from app.models import User
from app.schemas import user as user_schemas


def get_profile(db: Session, user: User) -> user_schemas.UserProfileResponse:
    return user_schemas.UserProfileResponse.model_validate(user)


def update_profile(db: Session, user: User, data: user_schemas.UserUpdateRequest) -> User:
    if data.full_name is not None:
        user.full_name = data.full_name

    if data.new_password is not None:
        if not data.current_password:
            raise bad_request("current_password is required to change your password.")
        if not security.password_hasher.verify(data.current_password, user.hashed_password):
            raise unauthorized("Current password is incorrect.", code="invalid_credentials")
        user.hashed_password = security.password_hasher.hash(data.new_password)

    if data.current_password is not None and data.new_password is None:
        raise bad_request("new_password is required when providing current_password.")

    db.flush()
    return user
