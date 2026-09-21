"""Version 1 API router assembly."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    analysis_sessions,
    auth,
    geometries,
    health,
    organizations,
    places,
    satellite,
    saved_locations,
    users,
    workspaces,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(organizations.router)
api_router.include_router(workspaces.router)
api_router.include_router(saved_locations.router)
api_router.include_router(places.router)
api_router.include_router(geometries.router)
api_router.include_router(analysis_sessions.router)
api_router.include_router(satellite.router)
