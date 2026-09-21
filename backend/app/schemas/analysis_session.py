"""Analysis-session schemas (Phase 3: AOI, date range, agent selection).

Configuration is stored on the session row so that a future phase can build
analysis requests (satellite scenes, weather, agent runs) from a re-opened
session. The AOI is kept as a GeoJSON geometry in requests and responses.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Agent codes selectable for an analysis session.
AGENT_CODES = ("agri", "aqua", "weather", "change")

SESSION_STATUSES = ("draft", "queued", "running", "completed", "failed")


class AnalysisSessionBase(BaseModel):
    workspace_id: int | None = None
    title: str | None = Field(default=None, max_length=255)
    aoi: dict[str, Any] | None = None  # GeoJSON geometry / Feature / FeatureCollection
    saved_location_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    agents: list[str] | None = None  # validated to AGENT_CODES by the service


class AnalysisSessionCreate(AnalysisSessionBase):
    pass


class AnalysisSessionUpdate(AnalysisSessionBase):
    pass


class AnalysisSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    workspace_id: int | None = None
    title: str
    status: str
    aoi: dict[str, Any] | None = None  # GeoJSON geometry
    start_date: date | None = None
    end_date: date | None = None
    agents: list[str] | None = None
    bbox: list[float] | None = None
    centroid: dict[str, float] | None = None  # {"lon": ..., "lat": ...}
    area_m2_approx: float = 0.0
    created_at: datetime
    updated_at: datetime
