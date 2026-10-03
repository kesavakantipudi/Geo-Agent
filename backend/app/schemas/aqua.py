"""Water intelligence schemas (Phase 6B).

Analysis is anchored to an analysis session (its AOI and access rules) and a
satellite scene, exactly like agricultural intelligence. Requests name the
``ndwi`` index plus an optional documented water ``threshold`` override. Results
are **derived on demand** — nothing is persisted — so a completed result carries
statistics, water/non-water classification, and full provenance, while a
computation that cannot be performed faithfully returns
``status == "unavailable"`` with a structured reason (never fabricated numbers).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

SUPPORTED_INDICES: tuple[str, ...] = ("ndwi",)


class AquaAnalyzeRequest(BaseModel):
    analysis_session_id: int
    scene_id: int
    # Optional per-call AOI override; defaults to the session AOI when omitted.
    aoi: dict[str, Any] | None = None
    indices: list[str] = Field(default_factory=lambda: ["ndwi"])
    mask_clouds: bool = True
    # Documented water threshold (default aqua_water_threshold when omitted).
    threshold: float | None = None


class AquaIndexInfo(BaseModel):
    name: str
    label: str
    formula: str
    band_roles: dict[str, str]
    units: str
    range: list[float]
    description: str


class AquaBandOutput(BaseModel):
    role: str
    asset_key: str
    retrieval_id: int


class AquaCloudInfo(BaseModel):
    mask_clouds: bool
    cloud_mask_available: bool
    masked_classes: list[int]


class AquaStatistics(BaseModel):
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


class AquaWaterSummary(BaseModel):
    pixel_count: int
    pixel_pct: float
    area_m2: float
    pct_of_aoi_area: float


class AquaNonWaterSummary(BaseModel):
    pixel_count: int
    pixel_pct: float
    area_m2: float


class AquaClassification(BaseModel):
    label: str
    threshold: float
    boundary: str
    threshold_source: str
    water: AquaWaterSummary
    non_water: AquaNonWaterSummary
    invalid_pixel_count: int
    aoi_area_m2: float


class AquaSceneReference(BaseModel):
    id: int
    provider: str
    scene_id: str
    platform: str | None = None
    acquisition_date: date
    cloud_cover: float | None = None


class AquaProcessingInfo(BaseModel):
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


class AquaUnavailableInfo(BaseModel):
    code: str
    reason: str
    details: list[str] = []


class AquaAnalysisResult(BaseModel):
    status: Literal["completed", "unavailable"]
    scene: AquaSceneReference
    index: AquaIndexInfo | None = None
    acquisition_date: date | None = None
    cloud: AquaCloudInfo | None = None
    statistics: AquaStatistics | None = None
    classification: AquaClassification | None = None
    bands: list[AquaBandOutput] | None = None
    processing: AquaProcessingInfo | None = None
    warnings: list[str] = []
    unavailable: AquaUnavailableInfo | None = None


class AquaAnalyzeResponse(BaseModel):
    results: list[AquaAnalysisResult]
