"""Change-detection raster alignment (Phase 6D).

Comparing two satellite observations pixel-by-pixel requires a shared grid.
The "before" scene's analysis window grid is the reference: both scenes produce
windowed index arrays over the same AOI, and the "after" array is resampled onto
the before grid with **nearest-neighbour** resampling only, so no interpolation
ever invents reflectance/index values. Alignment refuses to proceed when the
scenes are not comparable on a common grid (different CRS, rotated grids, or
materially different pixel resolution), because a comparison on such grids
would not be pixel-to-pixel meaningful.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from pyproj import Transformer
from rasterio.crs import CRS

from app.services.geospatial.raster import reproject_nearest

CSSRID = "EPSG:4326"


def to_crs(value: Any) -> CRS:
    """Best-effort CRS object from the serialized grid ``crs`` string."""
    return CRS.from_user_input(value)


def extract_grid(processing: dict[str, Any]) -> dict[str, Any]:
    """Pull the additive ``grid`` block out of an index ``processing`` payload."""
    grid = processing.get("grid")
    if not isinstance(grid, dict):
        raise ValueError("The analysis processing payload carries no grid block.")
    return grid


def _north_up_ok(grid: dict[str, Any]) -> bool:
    transform = grid["transform"]
    return transform["b"] == 0.0 and transform["d"] == 0.0


def _resolution_m(grid: dict[str, Any]) -> tuple[float, float]:
    return (float(abs(grid["transform"]["a"])), float(abs(grid["transform"]["e"])))


def verify_alignment(
    grid_before: dict[str, Any],
    grid_after: dict[str, Any],
    *,
    resolution_tolerance_ratio: float = 1e-3,
) -> tuple[bool, dict[str, Any] | None]:
    """Return ``(compatible, alignment_info)`` for the two window grids.

    Compatible requires: equal CRS, north-up (unrotated) grids, and compatible
    east/north pixel resolutions (relative difference within
    ``resolution_tolerance_ratio``). On success the second value describes the
    resampling mode applied to the "after" grid: ``"none"`` when the grids are
    identical, otherwise ``"nearest"``.
    """
    mismatch: dict[str, Any] = {"grid_before": grid_before, "grid_after": grid_after}
    if not (_north_up_ok(grid_before) and _north_up_ok(grid_after)):
        return False, {"grid_before": grid_before, "grid_after": grid_after}
    try:
        crs_before = to_crs(grid_before["crs"])
        crs_after = to_crs(grid_after["crs"])
    except Exception:
        return False, mismatch
    if crs_before != crs_after:
        return False, mismatch
    east_before, nord_before = _resolution_m(grid_before)
    east_after, nord_after = _resolution_m(grid_after)
    east_ratio = abs(east_before - east_after) / max(east_before, east_after)
    nord_ratio = abs(nord_before - nord_after) / max(nord_before, nord_after)
    if east_ratio > resolution_tolerance_ratio or nord_ratio > resolution_tolerance_ratio:
        return False, mismatch

    same_grid = (
        grid_before["transform"] == grid_after["transform"]
        and grid_before["width"] == grid_after["width"]
        and grid_before["height"] == grid_after["height"]
    )
    mode = "none" if same_grid else "nearest"
    return True, {
        "mode": mode,
        "resampled_with": "nearest" if mode == "nearest" else None,
        "crs": str(grid_before["crs"]),
        "width": int(grid_before["width"]),
        "height": int(grid_before["height"]),
        "pixel_size_m": [east_before, nord_before],
        "note": (
            "Pixels compared on the before-scene grid; the after observation is "
            "resampled with nearest-neighbour (no interpolation invents values)."
            if mode == "nearest"
            else "Both observations already share exactly the same grid; no resampling was applied."
        ),
    }


def resample_nearest(
    values: np.ndarray,
    grid_before: dict[str, Any],
    grid_after: dict[str, Any],
    dst_shape: tuple[int, int],
) -> np.ndarray:
    """Nearest-neighbour resample a float32 array onto the before grid."""
    return reproject_nearest(
        source=values,
        src_transform=to_transform(grid_after),
        src_crs=to_crs(grid_after["crs"]),
        src_nodata=np.nan,
        dst_transform=to_transform(grid_before),
        dst_crs=to_crs(grid_before["crs"]),
        dst_shape=dst_shape,
        dst_nodata=np.nan,
    )


def to_transform(grid: dict[str, Any]):
    from affine import Affine

    t = grid["transform"]
    return Affine(t["a"], t["b"], t["c"], t["d"], t["e"], t["f"])


def window_bounds_ll(grid: dict[str, Any]) -> dict[str, float]:
    """EPSG:4326 bounding box of the before grid window ``{west,south,east,north}``."""
    transform = to_transform(grid)
    x0, y0 = transform @ (0, 0)
    x1, y1 = transform @ (int(grid["width"]), int(grid["height"]))
    transformer = Transformer.from_crs(to_crs(grid["crs"]), CSSRID, always_xy=True)
    corners = []
    for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        corners.append(transformer.transform(x, y))
    lons = [point[0] for point in corners]
    lats = [point[1] for point in corners]
    return {
        "west": float(min(lons)),
        "south": float(min(lats)),
        "east": float(max(lons)),
        "north": float(max(lats)),
    }
