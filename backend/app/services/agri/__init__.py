"""Agricultural intelligence orchestration (Phase 6A).

``compute_agri_index`` is a thin adapter over the shared windowed
normalized-difference analysis core (:mod:`app.services.geospatial.analysis`):
it turns a validated AOI plus locally retrieved satellite band files into a
deterministic index result — windowed reads (so large tiles stay cheap),
geodetically correct AOI masking, optional scene-classification masking, masked
statistics — and adds the agricultural-specific heuristic vegetation tiers.
Water intelligence (Phase 6B) consumes the same core with a water-tuned
classifier, so there is no duplicated processing pipeline.

Nothing here fabricates measurements. Any condition that prevents a faithful
computation is reported as an explicit "unavailable" payload (via
:class:`AgriUnavailable`) with the underlying reason preserved; the API never
returns made-up values for missing data.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.config import Settings
from app.services.agri import bands, classification
from app.services.agri.classification import HEURISTIC_NOTE
from app.services.agri.indices import IndexSpec
from app.services.geospatial.analysis import (
    IndexAnalysisUnavailable,
    analyze_index_ratio,
)
from app.services.geospatial.analysis import (
    index_info as index_info,
)
from app.services.geospatial.analysis import (
    window_for as window_for,
)
from app.services.geospatial.analysis import (
    window_pixel_count as window_pixel_count,
)


class AgriError(Exception):
    """Base error for agricultural intelligence failures."""


class AgriUnavailable(AgriError):
    """A computation could not be performed; carries a structured reason."""

    def __init__(self, code: str, reason: str, details: list[str] | None = None) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason
        self.details = details or []


def compute_agri_index(
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
    settings: Settings,
) -> dict[str, Any]:
    """Compute an index over the AOI from retrieved band files.

    ``band_paths`` maps roles ("red", "nir"[, "cloud_mask"]) to absolute file
    paths of the locally retrieved assets; ``band_retrievals`` maps the same
    roles to the satellite retrieval ids used, for provenance.
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
            max_window_pixels=settings.agri_max_window_pixels,
            min_valid_fraction=settings.agri_min_valid_fraction,
        )
    except IndexAnalysisUnavailable as exc:
        raise AgriUnavailable(exc.code, exc.reason, exc.details) from exc

    nd = result.pop("nd")
    nd_valid = result.pop("nd_valid")
    histogram = classification.tier_histogram(nd, nd_valid)
    dominant = classification.dominant_tier(histogram)
    overall = classification.tier_for_value(result["statistics"]["mean"])

    result["classification"] = {
        "overall": {
            "tier": overall["tier"],
            "label": overall["label"],
            "basis": "Mean NDVI of valid pixels.",
        },
        "dominant_tier": {
            "tier": dominant["tier"],
            "label": dominant["label"],
            "pixel_pct": dominant["pixel_pct"],
        },
        "tiers": histogram,
        "threshold_source": HEURISTIC_NOTE,
    }
    return result
