"""Change-detection orchestration (Phase 6D).

Compares two satellite observations of the same AOI pixel-by-pixel for a single
normalized-difference index (NDVI → vegetation change, NDWI → water extent
change). It reuses the exact shared index pipeline
(:func:`app.services.geospatial.analysis.analyze_index_ratio`) for each
observation — the same functions behind Agri and Aqua — and only adds the
*comparison* machinery:

1. both observations are analysed over the AOI on their own grids,
2. the two window grids are verified against a common north-up grid over the
   same CRS (aligning the "after" window onto the "before" grid with
   nearest-neighbour resampling when the grids differ),
3. change is classified over the comparison mask (valid in **both**), and
4. class masks, area statistics, and provenance are assembled.

Nothing is persisted and nothing is fabricated: an observation that cannot be
analysed, grids that cannot be aligned, or a comparison with no valid common
pixels raise :class:`ChangeDetectionUnavailable` with a structured reason.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np

from app.core.config import Settings
from app.services.change_detection import alignment, classification, encoding
from app.services.geospatial.analysis import (
    IndexAnalysisUnavailable,
    analyze_index_ratio,
    index_info,
)
from app.services.geospatial.indices import IndexSpec
from app.services.geospatial.raster import pixel_area_m2
from app.services.geospatial.statistics import describe, valid_fraction


class ChangeDetectionError(Exception):
    """Base error for change-detection failures."""


class ChangeDetectionUnavailable(ChangeDetectionError):
    """A change comparison could not be performed faithfully."""

    def __init__(self, code: str, reason: str, details: list[str] | None = None) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason
        self.details = details or []


def _run_scene_analysis(
    *,
    aoi_geojson: dict,
    index: IndexSpec,
    role_keys: dict[str, str],
    band_paths: dict[str, str],
    band_retrievals: dict[str, int],
    acquisition_date: date,
    cloud_cover: float | None,
    provider: str,
    platform: str | None,
    provider_scene_id: str | None,
    mask_clouds: bool,
    max_window_pixels: int,
    min_valid_fraction: float,
) -> dict[str, Any]:
    try:
        return analyze_index_ratio(
            aoi_geojson=aoi_geojson,
            index=index,
            band_role_keys=role_keys,
            band_paths=band_paths,
            band_retrievals=band_retrievals,
            acquisition_date=acquisition_date,
            cloud_cover=cloud_cover,
            provider=provider,
            platform=platform,
            provider_scene_id=provider_scene_id,
            mask_clouds=mask_clouds,
            max_window_pixels=max_window_pixels,
            min_valid_fraction=min_valid_fraction,
        )
    except IndexAnalysisUnavailable as exc:
        raise ChangeDetectionUnavailable(exc.code, exc.reason, exc.details) from exc


def compute_change_index(
    *,
    aoi_geojson: dict,
    index: IndexSpec,
    change_type: str,
    scene_before: dict[str, Any],
    scene_after: dict[str, Any],
    mask_clouds: bool,
    settings: Settings,
    change_threshold: float,
) -> dict[str, Any]:
    """Compute one change classification (``change_type`` in {vegetation, water}).

    ``scene_before``/``scene_after`` carry the resolved per-scene analysis inputs:
    ``role_keys``, ``band_paths``, ``band_retrievals``, ``acquisition_date``,
    ``cloud_cover``, ``provider``, ``platform``, ``provider_scene_id``.
    """
    max_window_pixels = settings.change_max_window_pixels
    min_valid_fraction = settings.change_min_valid_fraction

    before = _run_scene_analysis(
        aoi_geojson=aoi_geojson,
        index=index,
        mask_clouds=mask_clouds,
        max_window_pixels=max_window_pixels,
        min_valid_fraction=min_valid_fraction,
        **scene_before,
    )
    after = _run_scene_analysis(
        aoi_geojson=aoi_geojson,
        index=index,
        mask_clouds=mask_clouds,
        max_window_pixels=max_window_pixels,
        min_valid_fraction=min_valid_fraction,
        **scene_after,
    )
    return _compare_payloads(
        index=index,
        change_type=change_type,
        before=before,
        after=after,
        mask_clouds=mask_clouds,
        change_threshold=change_threshold,
        min_valid_fraction=min_valid_fraction,
    )


def _compare_payloads(
    *,
    index: IndexSpec,
    change_type: str,
    before: dict[str, Any],
    after: dict[str, Any],
    mask_clouds: bool,
    change_threshold: float,
    min_valid_fraction: float,
) -> dict[str, Any]:
    grid_before = alignment.extract_grid(before["processing"])
    grid_after = alignment.extract_grid(after["processing"])
    compatible, alignment_info = alignment.verify_alignment(grid_before, grid_after)
    if not compatible:
        raise ChangeDetectionUnavailable(
            "incompatible_raster_alignment",
            "The two observations are not on a comparable grid for pixel-level "
            "change detection; refusing to compare them.",
            details=[
                f"before_crs={grid_before.get('crs')}",
                f"after_crs={grid_after.get('crs')}",
                f"before_grid={grid_before.get('width')}x{grid_before.get('height')}",
                f"after_grid={grid_after.get('width')}x{grid_after.get('height')}",
                f"before_pixel_size_m={grid_before.get('pixel_size_m')}",
                f"after_pixel_size_m={grid_after.get('pixel_size_m')}",
            ],
        )

    rows, cols = int(grid_before["height"]), int(grid_before["width"])
    shape = (rows, cols)

    nd_before = before["nd"]
    nd_valid_before = before["nd_valid"]
    nd_after = after["nd"]
    nd_valid_after = after["nd_valid"]
    if alignment_info["mode"] == "nearest":
        nd_after = alignment.resample_nearest(nd_after, grid_before, grid_after, shape)
        nd_valid_after = (
            alignment.resample_nearest(
                nd_valid_after.astype(np.float32), grid_before, grid_after, shape
            )
            > 0.5
        )

    total_pixels = rows * cols
    comparison_valid = nd_valid_before & nd_valid_after
    comparison_count = int(comparison_valid.sum())
    comparison_pct = float(comparison_count / total_pixels * 100.0) if total_pixels else 0.0
    if comparison_count == 0 or (comparison_pct < min_valid_fraction * 100.0):
        raise ChangeDetectionUnavailable(
            "no_valid_comparison_pixels",
            f"Only {comparison_pct:.2f}% of the window has pixels valid in both "
            f"observations (minimum {min_valid_fraction * 100.0:.2f}% required); "
            "no faithful change comparison can be made.",
            details=[
                f"total_pixels={total_pixels}",
                f"comparison_valid_pixels={comparison_count}",
            ],
        )

    if change_type == "water":
        result = classification.water_change(
            nd_before, nd_after, nd_valid_before, nd_valid_after, change_threshold
        )
        summary = classification.water_summary(
            result, area_m2=pixel_area_m2(alignment.to_transform(grid_before))
        )
        label = "Water extent change (NDWI)"
        mask_classes = {
            "0": "unchanged (non-water)",
            "1": "new water",
            "2": "lost water",
            "3": "persistent water",
            "255": "invalid",
        }
    else:
        result = classification.vegetation_change(
            nd_before, nd_after, nd_valid_before, nd_valid_after, change_threshold
        )
        summary = classification.vegetation_summary(
            result, area_m2=pixel_area_m2(alignment.to_transform(grid_before))
        )
        label = "Vegetation change (NDVI)"
        mask_classes = {
            "0": "stable",
            "1": "increase",
            "2": "decrease",
            "255": "invalid",
        }

    cell_area = pixel_area_m2(alignment.to_transform(grid_before))
    before_stats = describe(nd_before, comparison_valid) or {}
    after_stats = describe(nd_after, comparison_valid) or {}
    delta_stats = describe(result["delta"], comparison_valid) or {} if "delta" in result else None

    return {
        "type": change_type,
        "status": "completed",
        "index": index_info(index),
        "bands": _scene_bands(before, "before") + _scene_bands(after, "after"),
        "cloud": {
            "mask_clouds": mask_clouds,
            "before": {
                "cloud_mask_available": before["cloud"]["cloud_mask_available"],
                "masked_classes": before["cloud"]["masked_classes"],
            },
            "after": {
                "cloud_mask_available": after["cloud"]["cloud_mask_available"],
                "masked_classes": after["cloud"]["masked_classes"],
            },
        },
        "comparison": {
            "grid": grid_before,
            "alignment": alignment_info,
            "masking": {
                "total_pixels": total_pixels,
                "before_valid_pixels": int(nd_valid_before.sum()),
                "before_valid_pct": valid_fraction(int(nd_valid_before.sum()), total_pixels),
                "after_valid_pixels": int(nd_valid_after.sum()),
                "after_valid_pct": valid_fraction(int(nd_valid_after.sum()), total_pixels),
                "comparison_valid_pixels": comparison_count,
                "comparison_valid_pct": round(comparison_pct, 4),
                "invalid_pixels": total_pixels - comparison_count,
            },
        },
        "statistics": {
            "computed_over": "Pixels valid in both observations (the comparison mask).",
            "before": {**before_stats, "valid_pixels": comparison_count},
            "after": {**after_stats, "valid_pixels": comparison_count},
            "delta": (
                {**delta_stats, "valid_pixels": comparison_count}
                if delta_stats is not None
                else None
            ),
        },
        "classification": {
            "label": label,
            "boundary": summary["boundary"],
            "threshold": summary["threshold"],
            "delta_range": summary.get("delta_range"),
            "water_extent": summary.get("water_extent"),
            "comparison_pixels": summary["comparison_pixels"],
            "classes": summary["classes"],
            "invalid_pixel_count": summary["invalid_pixel_count"],
            "limitations_note": summary["limitations_note"],
        },
        "mask": {
            "encoding": "image/png;base64",
            "data_uri": encoding.encode_mask_png(result["mask"]),
            "width": cols,
            "height": rows,
            "crs": str(grid_before["crs"]),
            "classes": mask_classes,
            "bounds": alignment.window_bounds_ll(grid_before),
            "pixel_area_m2": round(cell_area, 4),
        },
        "warnings": list(before["warnings"]) + list(after["warnings"]),
    }


def _scene_bands(payload: dict[str, Any], scene_label: str) -> list[dict[str, Any]]:
    return [{**entry, "scene": scene_label} for entry in payload.get("bands") or []]


def unavailable_block(change_type: str, exc: ChangeDetectionUnavailable) -> dict[str, Any]:
    """Build the per-type unavailable payload used by the service layer."""
    return {
        "type": change_type,
        "status": "unavailable",
        "unavailable": {
            "code": exc.code,
            "reason": exc.reason,
            "details": list(exc.details),
        },
        "warnings": [],
    }


__all__ = [
    "ChangeDetectionError",
    "ChangeDetectionUnavailable",
    "compute_change_index",
    "unavailable_block",
]
