"""Version 1 API router assembly."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, organizations, saved_locations, users, workspaces

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(organizations.router)
api_router.include_router(workspaces.router)
api_router.include_router(saved_locations.router)
