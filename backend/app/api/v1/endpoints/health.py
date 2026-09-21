"""Health and readiness endpoints. No credentials or internals are exposed."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import text

from app import __version__
from app.db.session import engine
from app.schemas.common import DatabaseHealthResponse, HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__, time=datetime.now(UTC))


@router.get(
    "/health/db",
    response_model=DatabaseHealthResponse,
    responses={503: {"description": "Database or PostGIS unavailable"}},
    tags=["health"],
)
def database_health() -> DatabaseHealthResponse:
    now = datetime.now(UTC)
    db_ok = False
    postgis_ok = False
    postgis_version: str | None = None
    try:
        with engine.connect() as connection:
            db_ok = connection.execute(text("SELECT 1")).scalar() == 1
            postgis_version = connection.execute(text("SELECT postgis_version()")).scalar()
            postgis_ok = bool(postgis_version)
    except Exception:  # noqa: BLE001 - health endpoint reports any failure
        db_ok = False
        postgis_ok = False
        postgis_version = None

    return DatabaseHealthResponse(
        status="ok" if (db_ok and postgis_ok) else "error",
        database=db_ok,
        postgis=postgis_ok,
        postgis_version=postgis_version,
        time=now,
    )
