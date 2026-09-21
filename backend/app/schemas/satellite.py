"""Satellite scene discovery and asset retrieval schemas (Phase 4).

Requests reference an analysis session (whose AOI and date range drive the
provider queries); responses expose scene metadata and download *statuses*
only. Download URLs are generated server-side at retrieval time and are never
returned to clients; only bounded on-demand downloads are supported.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

# Provider identifiers understood by the satellite service.
PROVIDER_NAMES = ("planetary-computer", "cdse")

RETRIEVAL_STATUSES = ("queued", "completed", "failed")


class SceneAsset(BaseModel):
    """A single data asset of a scene (key, media type, optional size)."""

    key: str
    href: str
    media_type: str | None = None
    size_bytes: int | None = None


class SceneSummary(BaseModel):
    id: int
    provider: str
    scene_id: str
    platform: str | None = None
    acquisition_date: date | None = None
    cloud_cover: float | None = None
    resolution_m: float | None = None
    # GeoJSON footprint as reported by the provider (SRID 4326).
    geometry: dict[str, Any] | None = None
    bbox: list[float] | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime
    assets: list[SceneAsset] = Field(default_factory=list)


class SceneSearchRequest(BaseModel):
    # Either an analysis session (recommended) or an inline AOI + dates.
    analysis_session_id: int | None = None
    # GeoJSON AOI override; when a session is given, this overrides its AOI.
    aoi: dict[str, Any] | None = None
    start_date: date | None = None
    end_date: date | None = None
    # Subset of enabled providers; defaults to all enabled providers.
    providers: list[str] | None = None
    limit: int = Field(default=20, ge=1, le=100)
    max_cloud_cover: float = Field(default=100.0, ge=0.0, le=100.0)


class ProviderStatus(BaseModel):
    provider: str
    scenes: int = 0
    error: str | None = None


class SceneSearchResponse(BaseModel):
    scenes: list[SceneSummary]
    providers: list[ProviderStatus]
    truncated: bool = False


class RetrievalRequest(BaseModel):
    asset_keys: list[str] = Field(min_length=1, max_length=8)
    # Optional session to attribute the download to (must be user-accessible).
    analysis_session_id: int | None = None


class RetrievalSummary(BaseModel):
    id: int
    scene_id: int
    analysis_session_id: int | None = None
    asset_key: str
    status: str
    size_bytes: int | None = None
    error: str | None = None
    requested_at: datetime
    completed_at: datetime | None = None
