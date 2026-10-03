"""Shared windowed spectral-index analysis core (Phase 6).

Every derived intelligence service (agriculture via NDVI, water via NDWI,
change/historical later) computes a normalized-difference index from retrieved
Sentinel-2 band files over a validated AOI. The machinery — windowed reads (so
large tiles stay cheap), geodetically correct AOI masking, optional scene
cloud-classification masking, masked statistics, and provenance assembly — is
implemented *once* here and reused by the domain wrappers, so there is no
duplicated processing pipeline.

A domain wrapper supplies an :class:`IndexSpec`-like object (duck-typed: name,
label, formula, band_roles, units, range_min/range_max, description,
zero_is_nodata, scl_masked_classes) plus the resolved role->asset-key mapping
and the retrieved band files. Nothing here fabricates measurements: any
condition that prevents a faithful computation raises
:class:`IndexAnalysisUnavailable` (mapped to a domain-specific unavailable
error by the wrapper) with the underlying reason preserved.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import rasterio
from numpy import version as numpy_version
from rasterio.errors import RasterioError

from app.services.geospatial.raster import (
    inside_aoi_mask,
    pixel_area_m2,
    project_bounds,
    raster_info,
    read_window,
    reproject_nearest,
    window_from_bounds,
)
from app.services.geospatial.statistics import describe, valid_fraction


class IndexAnalysisUnavailable(Exception):
    """A computation could not be performed; carries a structured reason."""

    def __init__(self, code: str, reason: str, details: list[str] | None = None) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason
        self.details = details or []


def normalized_difference(
    a: np.ndarray,
    b: np.ndarray,
    valid: np.ndarray,
    range_min: float,
    range_max: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Normalized-difference ratio ``(a - b) / (a + b)`` over ``valid`` cells.

    Pixels whose denominator is not positive (``a + b <= 0``), which cannot
    produce a meaningful ratio, are marked invalid and excluded from the result
    even when they were inside ``valid``; the remaining ratio is clipped to
    ``[range_min, range_max]`` and returned as float32. Any numerically
    degenerate input therefore stays invalid rather than producing a fabricated
    value.
    """
    denominator = a + b
    positive = denominator > 0.0
    nd = np.where(
        positive,
        (a - b) / np.where(positive, denominator, 1.0),
        np.nan,
    )
    nd = np.clip(nd, range_min, range_max).astype(np.float32)
    index_valid = valid & positive & np.isfinite(nd)
    return nd, index_valid


def index_info(index: Any) -> dict[str, Any]:
    """Serializable description of an index (formula, bands, range)."""
    return {
        "name": index.name,
        "label": index.label,
        "formula": index.formula,
        "band_roles": dict(index.band_roles),
        "units": index.units,
        "range": [index.range_min, index.range_max],
        "description": index.description,
    }


def window_pixel_count(window: Any) -> int:
    return int(window.width * window.height)


def window_for(
    path: str,
    aoi_bounds_ll: tuple[float, float, float, float],
    max_window_pixels: int,
    reason_role: str,
):
    """Read ``path`` windowed to the AOI bbox (bounded, clamped to the raster)."""
    try:
        transform, width, height, crs, _ = raster_info(path)
    except RasterioError as exc:
        raise IndexAnalysisUnavailable(
            "band_read_failed",
            f"The {reason_role} band file could not be opened for analysis: {exc}",
            details=[path],
        ) from exc
    try:
        raster_bounds = project_bounds(aoi_bounds_ll, crs)
    except Exception as exc:  # pyproj failure on unusual CRS
        raise IndexAnalysisUnavailable(
            "crs_transform_failed",
            f"The AOI could not be projected into the band coordinate system: {exc}",
        ) from exc
    try:
        window = window_from_bounds(raster_bounds, transform, width, height)
    except ValueError as exc:
        raise IndexAnalysisUnavailable(
            "no_overlap",
            "The AOI does not overlap the scene band footprint.",
            details=[str(exc)],
        ) from exc
    if window_pixel_count(window) > max_window_pixels:
        raise IndexAnalysisUnavailable(
            "aoi_window_too_large",
            "The AOI bounding box covers more pixels than allowed for a single "
            f"analysis ({window_pixel_count(window):,} > {max_window_pixels:,}). "
            "Draw a smaller AOI.",
        )
    return read_window(path, window)


def analyze_index_ratio(
    *,
    aoi_geojson: dict,
    index: Any,
    band_role_keys: dict[str, str],
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
    """Compute a normalized-difference index over the AOI from band files.

    ``band_role_keys`` maps semantic roles ("red"/"nir" or "green"/"nir", plus
    optionally "cloud_mask") to provider asset keys; ``band_paths`` and
    ``band_retrievals`` map the same roles to local file paths and retrieval
    ids. The returned dict carries the provenance/statistics payload plus the
    raw ``nd`` / ``nd_valid`` arrays for the domain wrapper to classify.
    """
    from shapely.geometry import shape as shapely_shape

    aoi_shape = shapely_shape(aoi_geojson)
    aoi_bounds_ll = tuple(float(value) for value in aoi_shape.bounds)

    numerator_role = index.numerator_role
    denominator_role = index.denominator_role
    roles = (numerator_role, denominator_role)
    for role in roles:
        if role not in band_paths:
            raise IndexAnalysisUnavailable(
                "bands_not_retrieved",
                f"Band assets required for this analysis have not been retrieved: {role}.",
                details=[f"missing_role={role}"],
            )
    numerator_win = window_for(
        band_paths[numerator_role], aoi_bounds_ll, max_window_pixels, numerator_role
    )
    denominator_win = window_for(
        band_paths[denominator_role], aoi_bounds_ll, max_window_pixels, denominator_role
    )
    band_shape = numerator_win.values.shape
    if denominator_win.values.shape != band_shape or numerator_win.crs != denominator_win.crs:
        raise IndexAnalysisUnavailable(
            "band_grid_mismatch",
            "The spectral bands are on different grids; cannot combine them "
            "without resampling reflectance (refused).",
            details=[
                f"{numerator_role}={numerator_win.values.shape}@{numerator_win.crs}",
                f"{denominator_role}={denominator_win.values.shape}@{denominator_win.crs}",
            ],
        )

    inside = inside_aoi_mask(aoi_geojson, numerator_win.transform, band_shape, numerator_win.crs)

    numerator_valid = ~numerator_win.nodata_mask
    denominator_valid = ~denominator_win.nodata_mask
    if index.zero_is_nodata:
        numerator_valid &= ~(numerator_win.values == 0)
        denominator_valid &= ~(denominator_win.values == 0)
    index_valid = numerator_valid & denominator_valid & inside

    warning: str | None = None
    cloud_mask_available = False
    if mask_clouds:
        cloud_path = band_paths.get("cloud_mask")
        if not cloud_path:
            warning = (
                "Cloud masking was requested but the scene has no cloud "
                "classification (SCL) asset; the analysis is unmasked."
            )
        else:
            try:
                cloud_window = window_for(
                    cloud_path, aoi_bounds_ll, max_window_pixels, "cloud classification"
                )
                if cloud_window.values.shape != band_shape:
                    cloud_grid = reproject_nearest(
                        cloud_window.values,
                        cloud_window.transform,
                        cloud_window.crs,
                        None,
                        numerator_win.transform,
                        numerator_win.crs,
                        band_shape,
                        np.nan,
                    )
                else:
                    cloud_grid = cloud_window.values
                cloud = np.isin(cloud_grid, index.scl_masked_classes)
                index_valid &= ~cloud
                cloud_mask_available = True
            except RasterioError as exc:
                warning = (
                    "Cloud masking was requested but the SCL band could not be "
                    f"read; the analysis is unmasked ({exc})."
                )

    total_aoi_pixels = int(inside.sum())
    valid_pixel_count = int(index_valid.sum())
    valid_pct = valid_fraction(valid_pixel_count, total_aoi_pixels)
    if valid_pixel_count == 0 or valid_pct < min_valid_fraction * 100.0:
        raise IndexAnalysisUnavailable(
            "insufficient_valid_pixels",
            f"Only {valid_pct:.2f}% of the AOI has valid pixels (minimum "
            f"{min_valid_fraction * 100.0:.2f}% required). Clouds, cloud shadows, "
            "or no-data coverage removed the rest.",
            details=[f"valid={valid_pixel_count}", f"aoi_pixels={total_aoi_pixels}"],
        )

    nd, nd_valid = normalized_difference(
        numerator_win.values,
        denominator_win.values,
        index_valid,
        index.range_min,
        index.range_max,
    )
    stats = describe(nd, nd_valid)

    cell_area = pixel_area_m2(numerator_win.transform)
    warnings: list[str] = []
    if warning:
        warnings.append(warning)

    return {
        "nd": nd,
        "nd_valid": nd_valid,
        "status": "completed",
        "index": index_info(index),
        "cloud": {
            "mask_clouds": mask_clouds,
            "cloud_mask_available": cloud_mask_available,
            "masked_classes": [int(value) for value in index.scl_masked_classes],
        },
        "statistics": {
            **stats,
            "valid_pixel_count": valid_pixel_count,
            "aoi_pixel_count": total_aoi_pixels,
            "valid_pixel_pct": valid_pct,
            "excluded_pixel_pct": round(100.0 - valid_pct, 4),
            "sampled_area_m2": round(float(valid_pixel_count * cell_area), 2),
            "units": index.units,
            "range": [index.range_min, index.range_max],
        },
        "bands": [
            {
                "role": role,
                "asset_key": key,
                "retrieval_id": band_retrievals[role],
            }
            for role, key in band_role_keys.items()
            if role in band_retrievals
        ],
        "processing": {
            "algorithm": f"geoagent-{index.name}-v1",
            "processor": "geoagent-backend",
            "libraries": {
                "numpy": numpy_version.version,
                "rasterio": rasterio.__version__,
            },
            "acquisition_date": acquisition_date.isoformat(),
            "cloud_cover": cloud_cover,
            "provider": provider,
            "platform": platform,
            "provider_scene_id": provider_scene_id,
            "mask_clouds": mask_clouds,
            "cloud_mask_available": cloud_mask_available,
            "scl_masked_classes": [int(value) for value in index.scl_masked_classes],
            "zero_as_nodata": index.zero_is_nodata,
            "window": {"width": int(band_shape[1]), "height": int(band_shape[0])},
            "pixel_area_m2": round(cell_area, 4),
            "valid_pixel_area_m2": round(float(valid_pixel_count * cell_area), 2),
        },
        "warnings": warnings,
    }
