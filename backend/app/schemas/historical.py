"""Historical-intelligence schemas (Phase 6E).

The historical analysis is anchored to an analysis session (its AOI, access
rules, and date range) and constructs a **timeline over the session's
discovered scenes**: every observation is analyzed per requested type, ordered
by acquisition date (oldest → newest), aligned with weather context (descriptive
only, never causal), and consecutive observations are compared by reusing the
change-detection engine (Phase 6D) into deterministic, evidence-based events.

Results are **derived on demand** — nothing is persisted. Missing data is
reported as an explicit ``status == "unavailable"`` node with a structured
reason; it is never coerced to zero. ``coverage`` states how complete the
timeline is (including zero/one/sparse scenes and temporal gaps), and trends are
purely descriptive (first/latest/min/max + change), with the observation count
that actually supports them.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.change_detection import (
    ChangeIndexInfo,
    ChangeMask,
    ChangeStatistics,
    ChangeUnavailableInfo,
)
from app.schemas.weather import WeatherContext

SUPPORTED_HISTORICAL_TYPES: tuple[str, ...] = ("vegetation", "water")


class HistoricalRequest(BaseModel):
    """Request for a derived-on-demand historical timeline over a session."""

    analysis_session_id: int
    # Subset of SUPPORTED_HISTORICAL_TYPES to build into the timeline.
    types: list[str] = Field(default_factory=lambda: ["vegetation", "water"])
    mask_clouds: bool = True
    include_weather: bool = True
    # Documented heuristic over the resampled-NDVI delta for vegetation events.
    # Defaults to change_vegetation_threshold when omitted; validated (0, 2].
    vegetation_threshold: float | None = None
    # Water boundary reused from the Aqua analysis; validated [-1, 1].
    water_threshold: float | None = None
    # Optional range override; when the session has a date range this override
    # must stay within it. The session remains authoritative for AOI and access.
    start_date: date | None = None
    end_date: date | None = None


class HistoricalSceneRef(BaseModel):
    id: int
    scene_id: str
    provider: str
    platform: str | None = None
    acquisition_date: date
    cloud_cover: float | None = None
    # Provider metadata (constellation/instrument/processing_level/title).
    metadata: dict[str, Any] | None = None


class HistoricalMetricStatistics(BaseModel):
    min: float | None = None
    max: float | None = None
    mean: float | None = None
    median: float | None = None
    stddev: float | None = None
    valid_pixel_count: int
    aoi_pixel_count: int
    valid_pixel_pct: float
    excluded_pixel_pct: float
    sampled_area_m2: float
    units: str
    range: list[float]


class HistoricalVegetationMetric(BaseModel):
    """Per-observation NDVI metric; ``unavailable`` never fabricates a value."""

    status: Literal["completed", "unavailable"]
    index: ChangeIndexInfo | None = None
    statistics: HistoricalMetricStatistics | None = None
    warnings: list[str] = []
    unavailable: ChangeUnavailableInfo | None = None


class HistoricalWaterSummary(BaseModel):
    pixel_count: int
    # Share of the observation's *valid* pixels classified as water.
    pixel_pct: float
    area_m2: float
    pct_of_aoi_area: float
    aoi_area_m2: float


class HistoricalWaterMetric(BaseModel):
    """Per-observation NDWI metric; ``unavailable`` never fabricates a value."""

    status: Literal["completed", "unavailable"]
    index: ChangeIndexInfo | None = None
    statistics: HistoricalMetricStatistics | None = None
    water: HistoricalWaterSummary | None = None
    warnings: list[str] = []
    unavailable: ChangeUnavailableInfo | None = None


class HistoricalObservation(BaseModel):
    """One satellite observation on the timeline, ordered oldest → newest."""

    date: date
    index: int  # 0-based chronological position within the timeline
    scene: HistoricalSceneRef
    vegetation: HistoricalVegetationMetric | None = None
    water: HistoricalWaterMetric | None = None
    weather_context: WeatherContext | None = None


class HistoricalEventClassArea(BaseModel):
    pixel_count: int
    pixel_pct: float
    area_m2: float | None = None


class HistoricalChangedRegion(BaseModel):
    increased: HistoricalEventClassArea | None = None
    decreased: HistoricalEventClassArea | None = None
    stable: HistoricalEventClassArea | None = None
    changed_total: HistoricalEventClassArea | None = None


class HistoricalWaterExtent(BaseModel):
    before_pixels: int
    after_pixels: int
    delta_pixels: int
    before_pct: float
    after_pct: float
    added: HistoricalEventClassArea | None = None
    lost: HistoricalEventClassArea | None = None
    persistent: HistoricalEventClassArea | None = None
    unchanged: HistoricalEventClassArea | None = None


class HistoricalEventClassification(BaseModel):
    """Deterministic event classification for one consecutive-scene comparison."""

    event: str  # vegetation_increase | vegetation_decrease | vegetation_stable |
    #             water_expansion | water_reduction | water_stable
    label: str
    basis: str
    threshold: float
    boundary: str
    comparison_pixels: int
    comparison_valid_pct: float
    limitations_note: str
    region: HistoricalChangedRegion | None = None
    water_extent: HistoricalWaterExtent | None = None


class HistoricalEvent(BaseModel):
    """An observed change between two consecutive observations (or unavailable)."""

    type: Literal["vegetation", "water"]
    status: Literal["completed", "unavailable"]
    start_date: date
    end_date: date
    gap_days: int
    before: HistoricalSceneRef | None = None
    after: HistoricalSceneRef | None = None
    statistics: ChangeStatistics | None = None
    classification: HistoricalEventClassification | None = None
    mask: ChangeMask | None = None
    warnings: list[str] = []
    unavailable: ChangeUnavailableInfo | None = None


class HistoricalTrendPoint(BaseModel):
    date: date
    value: float | None  # vegetation: mean NDVI; water: water area_m2
    valid_pixel_pct: float | None


class HistoricalTrend(BaseModel):
    """Descriptive trend over completed observations; no extrapolation."""

    type: str
    observations: int  # completed observations contributing to the trend
    period: dict[str, date | None]
    first: HistoricalTrendPoint | None
    latest: HistoricalTrendPoint | None
    minimum: HistoricalTrendPoint | None
    maximum: HistoricalTrendPoint | None
    absolute_change: float | None
    relative_change_pct: float | None
    basis: str
    note: str


class HistoricalCoverageGap(BaseModel):
    from_date: date
    to_date: date
    gap_days: int


class HistoricalCoverage(BaseModel):
    observation_count: int
    start_date: date | None
    end_date: date | None
    temporal_span_days: int | None
    ordered_by: str
    gaps: list[HistoricalCoverageGap]
    compared_pairs: int
    same_day_pairs_skipped: int
    limited: bool
    notes: list[str]


class HistoricalProvenance(BaseModel):
    engine_version: str
    derived_on_demand: bool
    ordering_semantics: str
    change_reuse: str
    area_method: str
    libraries: dict[str, str]
    analyzed_at: str


class HistoricalResponse(BaseModel):
    status: Literal["completed", "unavailable"]
    # Authoritative session reference: id/title/start_date/end_date.
    session: dict[str, Any]
    types_requested: list[str]
    coverage: HistoricalCoverage
    observations: list[HistoricalObservation]
    events: list[HistoricalEvent]
    trends: dict[str, HistoricalTrend]
    # One weather context per observation (ordered oldest → newest) when
    # ``include_weather`` is true; descriptive context only.
    weather_contexts: list[WeatherContext] | None
    summary: str
    provenance: HistoricalProvenance
    warnings: list[str] = []
    unavailable: ChangeUnavailableInfo | None = None
