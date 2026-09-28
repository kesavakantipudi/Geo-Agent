"""Agricultural intelligence orchestration (Phase 6A).

``compute_agri_index`` turns a validated AOI plus locally retrieved satellite
band files into a deterministic index result: windowed reads (so large tiles
stay cheap), geodetically correct AOI masking, optional scene-classification
masking, masked statistics, and documented heuristic vegetation tiers.

Nothing here fabricates measurements. Any condition that prevents a faithful
computation is reported as an explicit "unavailable" payload (via
:class:`AgriUnavailable`) with the underlying reason preserved; the API never
returns made-up values for missing data.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import rasterio
from numpy import version as numpy_version
from rasterio.errors import RasterioError
from shapely.geometry import shape as shapely_shape

from app.core.config import Settings
from app.services.agri import bands, classification, statistics
from app.services.agri.classification import HEURISTIC_NOTE
from app.services.agri.indices import IndexSpec, compute_ndvi
from app.services.geospatial.raster import (
    inside_aoi_mask,
    pixel_area_m2,
    project_bounds,
    raster_info,
    read_window,
    reproject_nearest,
    window_from_bounds,
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


def index_info(index: IndexSpec) -> dict[str, Any]:
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


# ---------------------------------------------------------------------------
# Computation core
# ---------------------------------------------------------------------------


def _window_for(
    path: str,
    aoi_bounds_ll: tuple[float, float, float, float],
    max_window_pixels: int,
) -> object:
    """Read ``path`` windowed to the AOI bbox (bounded, clamped to the raster)."""
    try:
        transform, width, height, crs, _ = raster_info(path)
    except RasterioError as exc:
        raise AgriUnavailable(
            "band_read_failed",
            f"The band file could not be opened for analysis: {exc}",
            details=[path],
        ) from exc
    try:
        raster_bounds = project_bounds(aoi_bounds_ll, crs)
    except Exception as exc:  # pyproj failure on unusual CRS
        raise AgriUnavailable(
            "crs_transform_failed",
            f"The AOI could not be projected into the band coordinate system: {exc}",
        ) from exc
    try:
        window = window_from_bounds(raster_bounds, transform, width, height)
    except ValueError as exc:
        raise AgriUnavailable(
            "no_overlap",
            "The AOI does not overlap the scene band footprint.",
            details=[str(exc)],
        ) from exc
    if window_pixel_count(window) > max_window_pixels:
        raise AgriUnavailable(
            "aoi_window_too_large",
            "The AOI bounding box covers more pixels than allowed for a single "
            f"analysis ({window_pixel_count(window):,} > {max_window_pixels:,}). "
            "Draw a smaller AOI.",
        )
    return read_window(path, window)


def window_pixel_count(window) -> int:
    return int(window.width * window.height)


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
    aoi_shape = shapely_shape(aoi_geojson)
    aoi_bounds_ll = tuple(float(value) for value in aoi_shape.bounds)

    red_win = _window_for(band_paths["red"], aoi_bounds_ll, settings.agri_max_window_pixels)
    nir_win = _window_for(band_paths["nir"], aoi_bounds_ll, settings.agri_max_window_pixels)
    band_shape = red_win.values.shape
    if nir_win.values.shape != band_shape or red_win.crs != nir_win.crs:
        raise AgriUnavailable(
            "band_grid_mismatch",
            "The RED and NIR bands are on different grids; cannot combine them "
            "without resampling reflectance (refused).",
            details=[
                f"red={red_win.values.shape}@{red_win.crs}",
                f"nir={nir_win.values.shape}@{nir_win.crs}",
            ],
        )

    inside = inside_aoi_mask(aoi_geojson, red_win.transform, band_shape, red_win.crs)

    red_valid = ~red_win.nodata_mask
    nir_valid = ~nir_win.nodata_mask
    if index.zero_is_nodata:
        red_valid &= ~(red_win.values == 0)
        nir_valid &= ~(nir_win.values == 0)
    index_valid = red_valid & nir_valid & inside

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
                scl_win = _window_for(cloud_path, aoi_bounds_ll, settings.agri_max_window_pixels)
                if scl_win.values.shape != band_shape:
                    scl_grid = reproject_nearest(
                        scl_win.values,
                        scl_win.transform,
                        scl_win.crs,
                        None,
                        red_win.transform,
                        red_win.crs,
                        band_shape,
                        np.nan,
                    )
                else:
                    scl_grid = scl_win.values
                cloud = np.isin(scl_grid, index.scl_masked_classes)
                index_valid &= ~cloud
                cloud_mask_available = True
            except RasterioError as exc:
                warning = (
                    "Cloud masking was requested but the SCL band could not be "
                    f"read; the analysis is unmasked ({exc})."
                )

    total_aoi_pixels = int(inside.sum())
    valid_pixel_count = int(index_valid.sum())
    valid_pct = statistics.valid_fraction(valid_pixel_count, total_aoi_pixels)
    if valid_pixel_count == 0 or valid_pct < settings.agri_min_valid_fraction * 100.0:
        raise AgriUnavailable(
            "insufficient_valid_pixels",
            f"Only {valid_pct:.2f}% of the AOI has valid pixels (minimum "
            f"{settings.agri_min_valid_fraction * 100.0:.2f}% required). Clouds, "
            "cloud shadows, or no-data coverage removed the rest.",
            details=[f"valid={valid_pixel_count}", f"aoi_pixels={total_aoi_pixels}"],
        )

    ndvi, ndvi_valid = compute_ndvi(red_win.values, nir_win.values, index_valid)
    stats = statistics.describe(ndvi, ndvi_valid)
    histogram = classification.tier_histogram(ndvi, ndvi_valid)
    dominant = classification.dominant_tier(histogram)
    overall = classification.tier_for_value(stats["mean"])

    cell_area = pixel_area_m2(red_win.transform)
    warnings: list[str] = []
    if warning:
        warnings.append(warning)

    return {
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
        "classification": {
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
        },
        "bands": [
            {
                "role": role,
                "asset_key": key,
                "retrieval_id": band_retrievals[role],
            }
            for role, key in bands.resolve_band_keys(provider, index.name).items()
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
