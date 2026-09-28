"""Agricultural intelligence schemas (Phase 6A).

Analysis is anchored to an analysis session (its AOI and access rules) and a
satellite scene. Requests name one or more *indices*; currently only ``ndvi``
is registered. A computation that cannot be performed faithfully (missing band
assets, unsupported provider, AOI outside the scene, essentially all pixels
masked) is returned as ``status == "unavailable"`` with a structured reason —
never as fabricated numbers. Completed results carry statistics, documented
heuristic tier thresholds, band provenance, and processing metadata.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

SUPPORTED_INDICES: tuple[str, ...] = ("ndvi",)


class AgriAnalyzeRequest(BaseModel):
    analysis_session_id: int
    scene_id: int
    # Optional per-call AOI override; defaults to the session AOI when omitted.
    aoi: dict[str, Any] | None = None
    indices: list[str] = Field(default_factory=lambda: ["ndvi"])
    mask_clouds: bool = True


class AgriIndexInfo(BaseModel):
    name: str
    label: str
    formula: str
    band_roles: dict[str, str]
    units: str
    range: list[float]
    description: str


class AgriBandOutput(BaseModel):
    role: str
    asset_key: str
    retrieval_id: int


class AgriCloudInfo(BaseModel):
    mask_clouds: bool
    cloud_mask_available: bool
    masked_classes: list[int]


class AgriStatistics(BaseModel):
    min: float
    max: float
    mean: float
    median: float
    stddev: float
    valid_pixel_count: int
    aoi_pixel_count: int
    valid_pixel_pct: float
    excluded_pixel_pct: float
    sampled_area_m2: float
    units: str
    range: list[float]


class AgriTier(BaseModel):
    tier: str
    label: str
    low: float | None = None
    high: float | None = None
    description: str
    pixel_pct: float


class AgriClassification(BaseModel):
    overall: dict[str, Any]
    dominant_tier: dict[str, Any]
    tiers: list[AgriTier]
    threshold_source: str


class AgriSceneReference(BaseModel):
    id: int
    provider: str
    scene_id: str
    platform: str | None = None
    acquisition_date: date
    cloud_cover: float | None = None


class AgriProcessingInfo(BaseModel):
    algorithm: str
    processor: str
    libraries: dict[str, str]
    acquisition_date: str
    cloud_cover: float | None = None
    provider: str
    platform: str | None = None
    provider_scene_id: str | None = None
    mask_clouds: bool
    cloud_mask_available: bool
    scl_masked_classes: list[int]
    zero_as_nodata: bool
    window: dict[str, int]
    pixel_area_m2: float
    valid_pixel_area_m2: float


class AgriUnavailableInfo(BaseModel):
    code: str
    reason: str
    details: list[str] = []


class AgriAnalysisResult(BaseModel):
    id: int | None = None
    status: Literal["completed", "unavailable"]
    scene: AgriSceneReference
    index: AgriIndexInfo | None = None
    acquisition_date: date | None = None
    cloud: AgriCloudInfo | None = None
    statistics: AgriStatistics | None = None
    classification: AgriClassification | None = None
    bands: list[AgriBandOutput] | None = None
    processing: AgriProcessingInfo | None = None
    warnings: list[str] = []
    unavailable: AgriUnavailableInfo | None = None
    created_at: datetime | None = None


class AgriAnalyzeResponse(BaseModel):
    results: list[AgriAnalysisResult]


class AgriAnalysisSummary(BaseModel):
    id: int
    status: str
    index_name: str
    acquisition_date: date
    scene_id: int
    provider: str
    platform: str | None = None
    cloud_cover: float | None = None
    overall_tier: str | None = None
    dominant_tier: str | None = None
    mean_value: float | None = None
    valid_pixel_pct: float | None = None
    created_at: datetime
