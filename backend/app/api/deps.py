"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core import security
from app.core.exceptions import unauthorized
from app.db.session import get_db
from app.models import User

DB_DEPENDENCY = Depends(get_db)


def _extract_access_token(request: Request) -> str | None:
    header = request.headers.get("authorization")
    if header and header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.cookies.get(security.ACCESS_COOKIE)


def get_current_user(request: Request, db: Session = DB_DEPENDENCY) -> User:
    token = _extract_access_token(request)
    if not token:
        raise unauthorized("Authentication required.")
    payload = security.decode_token(token, security.TOKEN_TYPE_ACCESS)
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise unauthorized("Account no longer exists.")
    if not user.is_active:
        raise unauthorized("This account is disabled.", code="account_disabled")
    return user


def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    return user


def get_refresh_token_from_request(request: Request) -> str | None:
    """Refresh token from cookie first, then Authorization/bearer body header."""
    cookie = request.cookies.get(security.REFRESH_COOKIE)
    if cookie:
        return cookie
    header = request.headers.get("x-refresh-token")
    if header:
        return header.strip()
    return None
