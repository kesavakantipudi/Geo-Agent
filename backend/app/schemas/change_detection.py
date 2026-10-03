"""Change-detection schemas (Phase 6D).

A comparison is anchored to an analysis session (its AOI and access rules) and
**two** satellite scenes the caller can access: ``before_scene_id`` (earlier)
and ``after_scene_id`` (later). Results are **derived on demand** — nothing is
persisted. Each requested change type (``vegetation`` via NDVI, ``water`` via
NDWI) is reported as a completed block carrying per-pixel class masks and area
statistics, or as an explicit ``status == "unavailable"`` block with a
structured reason — never fabricated numbers. The top-level response is
``completed`` when at least one requested type completed.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.weather import WeatherContext

SUPPORTED_CHANGE_TYPES: tuple[str, ...] = ("vegetation", "water")


class ChangeDetectionRequest(BaseModel):
    analysis_session_id: int
    before_scene_id: int
    after_scene_id: int
    # Optional per-call AOI override; defaults to the session AOI when omitted.
    aoi: dict[str, Any] | None = None
    types: list[str] = Field(default_factory=lambda: ["vegetation", "water"])
    mask_clouds: bool = True
    # Documented heuristic over the resampled-NDVI delta. Default
    # change_vegetation_threshold when omitted; validated (0, 2].
    vegetation_threshold: float | None = None
    # Water boundary reused from the Aqua analysis; validated [-1, 1].
    water_threshold: float | None = None
    include_weather: bool = True


class ChangeSceneRef(BaseModel):
    id: int
    scene_id: str
    provider: str
    platform: str | None = None
    acquisition_date: date
    cloud_cover: float | None = None
    # Provider metadata (constellation/instrument/processing_level/title).
    metadata: dict[str, Any] | None = None


class ChangeIndexInfo(BaseModel):
    name: str
    label: str
    formula: str
    band_roles: dict[str, str]
    units: str
    range: list[float]
    description: str


class ChangeBandOutput(BaseModel):
    scene: Literal["before", "after"]
    role: str
    asset_key: str
    retrieval_id: int


class ChangeCloudSide(BaseModel):
    cloud_mask_available: bool
    masked_classes: list[int]


class ChangeCloudInfo(BaseModel):
    mask_clouds: bool
    before: ChangeCloudSide
    after: ChangeCloudSide


class ChangeGrid(BaseModel):
    crs: str
    transform: dict[str, float]
    width: int
    height: int
    pixel_size_m: list[float]


class ChangeAlignment(BaseModel):
    mode: Literal["none", "nearest"]
    resampled_with: str | None = None
    crs: str
    width: int
    height: int
    pixel_size_m: list[float]
    note: str


class ChangeMasking(BaseModel):
    total_pixels: int
    before_valid_pixels: int
    before_valid_pct: float
    after_valid_pixels: int
    after_valid_pct: float
    comparison_valid_pixels: int
    comparison_valid_pct: float
    invalid_pixels: int


class ChangeComparison(BaseModel):
    grid: ChangeGrid
    alignment: ChangeAlignment
    masking: ChangeMasking


class ChangeStatBlock(BaseModel):
    min: float | None = None
    max: float | None = None
    mean: float | None = None
    median: float | None = None
    stddev: float | None = None
    valid_pixels: int


class ChangeStatistics(BaseModel):
    computed_over: str
    before: ChangeStatBlock
    after: ChangeStatBlock
    # NDVI delta stats; None for water (transitions, not a signed delta).
    delta: ChangeStatBlock | None = None


class ChangeClassSummary(BaseModel):
    pixel_count: int
    pixel_pct: float
    area_m2: float | None = None


class ChangeWaterExtent(BaseModel):
    before_pixels: int
    after_pixels: int
    delta_pixels: int
    before_pct: float
    after_pct: float


class ChangeClassification(BaseModel):
    label: str
    boundary: str
    threshold: float
    delta_range: list[float] | None = None
    water_extent: ChangeWaterExtent | None = None
    comparison_pixels: int
    classes: dict[str, Any]
    invalid_pixel_count: int
    limitations_note: str


class ChangeMask(BaseModel):
    encoding: str
    data_uri: str
    width: int
    height: int
    crs: str
    classes: dict[str, str]
    bounds: dict[str, float]
    pixel_area_m2: float


class ChangeUnavailableInfo(BaseModel):
    code: str
    reason: str
    details: list[str] = []


class ChangeTypeBlock(BaseModel):
    type: Literal["vegetation", "water"]
    status: Literal["completed", "unavailable"]
    index: ChangeIndexInfo | None = None
    bands: list[ChangeBandOutput] | None = None
    cloud: ChangeCloudInfo | None = None
    comparison: ChangeComparison | None = None
    statistics: ChangeStatistics | None = None
    classification: ChangeClassification | None = None
    mask: ChangeMask | None = None
    warnings: list[str] = []
    unavailable: ChangeUnavailableInfo | None = None


class ChangeProvenance(BaseModel):
    engine_version: str
    derived_on_demand: bool
    comparison_semantics: str
    invalid_is_change: bool
    resampling: str
    area_method: str
    libraries: dict[str, str]
    analyzed_at: str


class ChangeDetectionResponse(BaseModel):
    status: Literal["completed", "unavailable"]
    before: ChangeSceneRef
    after: ChangeSceneRef
    types_requested: list[str]
    vegetation: ChangeTypeBlock | None = None
    water: ChangeTypeBlock | None = None
    # Two weather contexts (before, after) around each observation when the
    # analysis was computed with ``include_weather`` (descriptive only).
    weather_contexts: list[WeatherContext] | None = None
    provenance: ChangeProvenance | None = None
    warnings: list[str] = []
    unavailable: ChangeUnavailableInfo | None = None
