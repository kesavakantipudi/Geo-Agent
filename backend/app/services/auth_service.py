"""Authentication business logic: registration, login, refresh rotation, logout."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import get_settings
from app.core.exceptions import conflict, unauthorized
from app.models import User
from app.schemas import auth as auth_schemas


def _find_user_by_identifier(db: Session, identifier: str) -> User | None:
    lower = identifier.lower()
    return db.execute(
        select(User).where(or_(User.email == lower, User.username == identifier))
    ).scalar_one_or_none()


def register(db: Session, data: auth_schemas.RegisterRequest) -> User:
    email = data.email.lower().strip()
    if db.execute(select(User).where(User.email == email)).scalar_one_or_none():
        raise conflict("An account with this email already exists.", code="email_taken")
    if db.execute(select(User).where(User.username == data.username)).scalar_one_or_none():
        raise conflict("This username is already taken.", code="username_taken")

    user = User(
        email=email,
        username=data.username,
        full_name=data.full_name,
        hashed_password=security.password_hasher.hash(data.password),
    )
    db.add(user)
    db.flush()
    return user


def login(db: Session, data: auth_schemas.LoginRequest) -> User:
    user = _find_user_by_identifier(db, data.identifier)
    if user is None or not security.password_hasher.verify(data.password, user.hashed_password):
        raise unauthorized("Incorrect email/username or password.", code="invalid_credentials")
    if not user.is_active:
        raise unauthorized("This account is disabled.", code="account_disabled")
    return user


def issue_token_pair(db: Session, user: User) -> auth_schemas.TokenResponse:
    """Create an access + refresh pair, persist the refresh token, and capture identity."""
    from app.models import RefreshToken

    access = security.create_access_token(user.id)
    refresh = security.create_refresh_token(user.id)
    expires_at = security.generate_refresh_token_expiry()

    previous = (
        db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
            )
        )
        .scalars()
        .all()
    )
    for record in previous:
        record.revoked_at = security.now_utc()

    jti = security.decode_token(refresh, security.TOKEN_TYPE_REFRESH)["jti"]
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=security.hash_token(refresh),
            jti=jti,
            expires_at=expires_at,
        )
    )
    db.flush()

    settings = get_settings()
    return auth_schemas.TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )


def rotate_refresh(db: Session, user: User, old_refresh: str) -> auth_schemas.TokenResponse:
    """Validate the presented refresh token, revoke it, and issue a fresh pair."""
    security.validate_refresh_token(db, old_refresh)
    security.revoke_refresh_token(db, old_refresh)
    return issue_token_pair(db, user)


def get_user_for_refresh(db: Session, refresh: str) -> User:
    payload = security.validate_refresh_token(db, refresh)
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise unauthorized("Account no longer exists or is disabled.")
    return user


def revoke_refresh(db: Session, refresh: str) -> bool:
    return security.revoke_refresh_token(db, refresh)
