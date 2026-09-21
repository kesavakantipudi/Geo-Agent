"""Authentication endpoints: register, login, refresh, logout, me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_refresh_token_from_request
from app.core import security
from app.core.exceptions import unauthorized
from app.db.session import get_db
from app.models import User
from app.schemas import auth as auth_schemas
from app.services import auth_service

router = APIRouter(tags=["auth"])

DB_DEPENDENCY = Depends(get_db)


@router.post(
    "/auth/register",
    response_model=auth_schemas.TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account and log in",
)
def register(data: auth_schemas.RegisterRequest, response: Response, db: Session = DB_DEPENDENCY):
    user = auth_service.register(db, data)
    tokens = auth_service.issue_token_pair(db, user)
    db.commit()
    security.set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return tokens


@router.post(
    "/auth/login",
    response_model=auth_schemas.TokenResponse,
    summary="Log in with email or username and password",
)
def login(data: auth_schemas.LoginRequest, response: Response, db: Session = DB_DEPENDENCY):
    user = auth_service.login(db, data)
    tokens = auth_service.issue_token_pair(db, user)
    db.commit()
    security.set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return tokens


@router.post(
    "/auth/refresh",
    response_model=auth_schemas.TokenResponse,
    summary="Rotate the refresh token and issue a fresh pair",
)
def refresh(
    data: auth_schemas.RefreshRequest,
    request: Request,
    response: Response,
    db: Session = DB_DEPENDENCY,
):
    token = data.refresh_token or get_refresh_token_from_request(request)
    if not token:
        raise unauthorized("No refresh token provided.")
    user = auth_service.get_user_for_refresh(db, token)
    tokens = auth_service.rotate_refresh(db, user, token)
    db.commit()
    security.set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return tokens


@router.post(
    "/auth/logout",
    response_model=auth_schemas.LogoutResponse,
    summary="Revoke the refresh token and clear cookies",
)
def logout(
    data: auth_schemas.RefreshRequest,
    request: Request,
    response: Response,
    db: Session = DB_DEPENDENCY,
):
    token = data.refresh_token or get_refresh_token_from_request(request)
    if token:
        auth_service.revoke_refresh(db, token)
        db.commit()
    security.clear_auth_cookies(response)
    return auth_schemas.LogoutResponse()


@router.get(
    "/auth/me", response_model=auth_schemas.AuthUserResponse, summary="Current authenticated user"
)
def me(user: User = Depends(get_current_user)):
    return user
