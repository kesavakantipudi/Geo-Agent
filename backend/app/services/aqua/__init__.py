"""Water intelligence orchestration (Phase 6B).

``compute_aqua_index`` is a thin adapter over the same shared windowed
normalized-difference analysis core used by agricultural intelligence
(:mod:`app.services.geospatial.analysis`): windowed reads, geodetically correct
AOI masking, optional scene-classification masking, and masked statistics. It
adds the water-specific classification — a documented heuristic threshold
(NDWI >= threshold is open water) with water/non-water pixel counts, masked
statistics, and water-area from the projected pixel grid. There is no duplicated
processing pipeline between agri and aqua.

Nothing here fabricates measurements. Any condition that prevents a faithful
computation is reported as an explicit "unavailable" payload (via
:class:`AquaUnavailable`) with the underlying reason preserved; the API never
returns made-up values for missing data.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.config import Settings
from app.services.agri import bands
from app.services.aqua import classification
from app.services.geospatial.analysis import (
    IndexAnalysisUnavailable,
    analyze_index_ratio,
)
from app.services.geospatial.indices import IndexSpec


class AquaError(Exception):
    """Base error for water intelligence failures."""


class AquaUnavailable(AquaError):
    """A computation could not be performed; carries a structured reason."""

    def __init__(self, code: str, reason: str, details: list[str] | None = None) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason
        self.details = details or []


def compute_aqua_index(
    *,
    aoi_geojson: dict,
    index: IndexSpec,
    band_paths: dict[str, str],
    band_retrievals: dict[str, int],
    acquisition_date: date,
    cloud_cover: float | None,
    provider: str,
    platform: str | None,
    provider_scene_id: str | None,
    mask_clouds: bool,
    threshold: float,
    settings: Settings,
) -> dict[str, Any]:
    """Compute NDWI over the AOI from retrieved band files.

    ``band_paths`` maps roles ("green", "nir"[, "cloud_mask"]) to absolute file
    paths of the locally retrieved assets; ``band_retrievals`` maps the same
    roles to the satellite retrieval ids used, for provenance. ``threshold`` is
    the documented water boundary (mirrors the per-analysis override and the
    ``aqua_water_threshold`` default); it is echoed in the classification block.
    """
    try:
        result = analyze_index_ratio(
            aoi_geojson=aoi_geojson,
            index=index,
            band_role_keys=bands.resolve_band_keys(provider, index.name),
            band_paths=band_paths,
            band_retrievals=band_retrievals,
            acquisition_date=acquisition_date,
            cloud_cover=cloud_cover,
            provider=provider,
            platform=platform,
            provider_scene_id=provider_scene_id,
            mask_clouds=mask_clouds,
            max_window_pixels=settings.aqua_max_window_pixels,
            min_valid_fraction=settings.aqua_min_valid_fraction,
        )
    except IndexAnalysisUnavailable as exc:
        raise AquaUnavailable(exc.code, exc.reason, exc.details) from exc

    nd = result.pop("nd")
    nd_valid = result.pop("nd_valid")
    result["classification"] = classification.water_summary(
        nd,
        nd_valid,
        threshold=threshold,
        valid_pixel_count=result["statistics"]["valid_pixel_count"],
        aoi_pixel_count=result["statistics"]["aoi_pixel_count"],
        pixel_area_m2=result["processing"]["pixel_area_m2"],
    )
    return result
