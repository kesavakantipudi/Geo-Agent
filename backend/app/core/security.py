"""Password hashing, JWT tokens, cookie helpers, and token persistence.

Security model (Phase 2):

- Passwords are hashed with Argon2 via ``pwdlib`` (never stored in plain text).
- JWT access tokens are short-lived (default 15 min) and carry a ``type`` claim
  so access and refresh tokens cannot be used interchangeably.
- Refresh tokens are opaque-ish bearer JWT values persisted (hashed with SHA-256)
  in the database. A refresh grants a *rotated* pair and revokes the previous
  refresh token, so a stolen refresh token can be invalidated on logout.
- Access/refresh JWTs are delivered in HttpOnly, SameSite=Lax cookies scoped to
  the backend. The browser origin proxied by the Next.js dev server is
  same-origin, which avoids cross-site cookie restrictions in local development.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt as pyjwt
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import unauthorized

ACCESS_COOKIE = "geoagent_access"
REFRESH_COOKIE = "geoagent_refresh"

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"

_ALGORITHMS = ["HS256", "HS384", "HS512"]


class PasswordHasher:
    """Argon2 password hashing facade."""

    def __init__(self) -> None:
        self._hasher = PasswordHash.recommended()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, hashed: str) -> bool:
        try:
            return self._hasher.verify(password, hashed)
        except Exception:  # noqa: BLE001 - any verification failure means "no match"
            return False


password_hasher = PasswordHasher()


def now_utc() -> datetime:
    return datetime.now(UTC)


def generate_jti() -> str:
    return uuid.uuid4().hex


def _encode(payload: dict[str, Any], expires_delta: timedelta) -> str:
    settings = get_settings()
    now = now_utc()
    payload = {
        "sub": str(payload["sub"]),
        "type": payload["type"],
        "jti": payload["jti"],
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return pyjwt.encode(payload, settings.auth_secret_key, algorithm=settings.auth_algorithm)


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    return _encode(
        {"sub": user_id, "type": TOKEN_TYPE_ACCESS, "jti": generate_jti()},
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: int) -> str:
    settings = get_settings()
    return _encode(
        {"sub": user_id, "type": TOKEN_TYPE_REFRESH, "jti": generate_jti()},
        timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    """Verify signature, expiry, and token type. Raises ``ApiError`` on failure."""
    settings = get_settings()
    try:
        payload = pyjwt.decode(
            token,
            settings.auth_secret_key,
            algorithms=_ALGORITHMS,
            options={"require": ["sub", "type", "jti", "exp", "iat"]},
        )
    except pyjwt.ExpiredSignatureError as exc:
        raise unauthorized("Your session has expired.") from exc
    except pyjwt.InvalidTokenError as exc:
        raise unauthorized("Invalid token.") from exc
    if payload.get("type") != expected_type:
        raise unauthorized("Token type mismatch.")
    return payload


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def tokens_are_equivalent(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return hmac.compare_digest(hash_token(a), hash_token(b))


# ---------------------------------------------------------------- cookies


def set_auth_cookies(response, access_token: str, refresh_token: str) -> None:
    settings = get_settings()
    secure = settings.is_production
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=settings.refresh_token_expire_days * 86400,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")


# ---------------------------------------------------------------- persistence


def persist_refresh_token(db: Session, user_id: int, token: str, expires_at: datetime) -> None:
    """Store a hashed refresh token, revoking any previous live one for the user."""
    from app.models import RefreshToken

    previous = (
        db.execute(select(RefreshToken).where(RefreshToken.user_id == user_id)).scalars().all()
    )
    for record in previous:
        if record.revoked_at is None:
            record.revoked_at = now_utc()
    new_jti = decode_token(token, TOKEN_TYPE_REFRESH)["jti"]
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hash_token(token),
            jti=new_jti,
            expires_at=expires_at,
        )
    )
    db.flush()


def revoke_refresh_token(db: Session, token: str) -> bool:
    """Revoke the refresh token identified by ``token``. Returns True if found."""
    from app.models import RefreshToken

    token_hash = hash_token(token)
    record = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).scalar_one_or_none()
    if record is None:
        return False
    if record.revoked_at is None:
        record.revoked_at = now_utc()
        db.flush()
    return True


def get_refresh_token_record(db: Session, token: str) -> Any | None:
    from app.models import RefreshToken

    return db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(token))
    ).scalar_one_or_none()


def validate_refresh_token(db: Session, token: str) -> dict[str, Any]:
    """Validate a refresh token at the database level and return its payload."""
    payload = decode_token(token, TOKEN_TYPE_REFRESH)
    record = get_refresh_token_record(db, token)
    if record is None:
        raise unauthorized("Refresh token is no longer valid.")
    if record.revoked_at is not None:
        raise unauthorized("Refresh token has been revoked.")
    if record.expires_at < now_utc():
        raise unauthorized("Refresh token has expired.")
    return payload


def generate_refresh_token_expiry() -> datetime:
    settings = get_settings()
    return now_utc() + timedelta(days=settings.refresh_token_expire_days)
