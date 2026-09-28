"""Windowed raster reading and AOI/cloud masking (Phase 6A).

GeoTIFF/COG band files retrieved for a satellite scene can be very large
(Sentinel-2 10 m tiles are 10980 x 10980), so all reads are windowed to the
bounding box of the analysis AOI (expanded to the raster grid, clamped to the
raster extent). Masks (AOI polygon, no-data, cloud classification bands) are
combined in the band grid, and misaligned auxiliary bands (e.g. the 20 m SCL
mask vs 10 m reflectance bands) are reprojected with nearest-neighbour
resampling so that no interpolation invents reflectance values.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.warp import reproject
from rasterio.windows import Window, from_bounds
from shapely.geometry import shape as shapely_shape
from shapely.ops import transform as shapely_transform

CSSRID = "EPSG:4326"


@dataclass
class RasterWindow:
    """A windowed slice of one raster band read from disk.

    ``values`` is float32 with no-data/nan cells converted to ``np.nan``;
    ``nodata_mask`` is True exactly where the source declared no-data (or the
    read produced a non-finite value). Both share the geometry defined by
    ``transform`` (row/col grid) and ``crs``.
    """

    values: np.ndarray
    nodata_mask: np.ndarray
    transform: Affine
    crs: CRS
    width: int
    height: int


def raster_info(path: str | Path) -> tuple[Affine, int, int, CRS, object]:
    """Return (transform, width, height, crs, nodata) for a band file."""
    with rasterio.open(path) as src:
        return (src.transform, src.width, src.height, src.crs, src.nodata)


def project_bounds(
    bounds: tuple[float, float, float, float], dst_crs: CRS
) -> tuple[float, float, float, float]:
    """Conservative bbox of ``bounds`` (lon/lat) expressed in ``dst_crs``."""
    transformer = Transformer.from_crs(CSSRID, dst_crs, always_xy=True)
    xs: list[float] = []
    ys: list[float] = []
    for sequence in (
        ((bounds[0], bounds[1]), (bounds[2], bounds[1])),
        ((bounds[0], bounds[3]), (bounds[2], bounds[3])),
    ):
        for x, y in sequence:
            px, py = transformer.transform(x, y)
            xs.append(float(px))
            ys.append(float(py))
    return min(xs), min(ys), max(xs), max(ys)


def window_from_bounds(
    bounds: tuple[float, float, float, float],
    transform: Affine,
    width: int,
    height: int,
) -> Window:
    """Clamp ``bounds`` (already in the raster CRS) to a window inside the grid."""
    raw = from_bounds(bounds[0], bounds[1], bounds[2], bounds[3], transform)
    col_off = max(0, int(np.floor(raw.col_off)))
    row_off = max(0, int(np.floor(raw.row_off)))
    col_stop = int(min(width, np.ceil(raw.col_off + raw.width)))
    row_stop = int(min(height, np.ceil(raw.row_off + raw.height)))
    if col_stop <= col_off or row_stop <= row_off:
        raise ValueError("AOI does not overlap this raster.")
    return Window(col_off, row_off, col_stop - col_off, row_stop - row_off)


def read_window(path: str | Path, window: Window) -> RasterWindow:
    """Read a sub-window of a single-band raster into a float32 RasterWindow."""
    with rasterio.open(path) as src:
        raw = src.read(1, window=window).astype(np.float32)
        transform = src.window_transform(window)
        crs = src.crs
        nodata = src.nodata
    not_finite = ~np.isfinite(raw)
    if nodata is not None:
        not_finite |= raw == np.float32(nodata)
    values = np.where(not_finite, np.nan, raw).astype(np.float32)
    return RasterWindow(
        values=values,
        nodata_mask=not_finite,
        transform=transform,
        crs=crs,
        width=int(window.width),
        height=int(window.height),
    )


def reproject_nearest(
    source: np.ndarray,
    src_transform: Affine,
    src_crs: CRS,
    src_nodata: object,
    dst_transform: Affine,
    dst_crs: CRS,
    dst_shape: tuple[int, int],
    dst_nodata: object,
) -> np.ndarray:
    """Nearest-neighbour resample ``source`` onto the ``dst_*`` grid."""
    destination = np.empty(dst_shape, dtype=np.float32)
    (destination, _) = reproject(
        source=source.astype(np.float32),
        destination=destination,
        src_transform=src_transform,
        src_crs=src_crs,
        src_nodata=src_nodata,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        dst_nodata=dst_nodata,
        resampling=Resampling.nearest,
    )
    return destination


def inside_aoi_mask(
    aoi_geojson: dict,
    transform: Affine,
    shape: tuple[int, int],
    crs: CRS,
) -> np.ndarray:
    """Boolean array (True = inside the AOI) on the window grid.

    ``aoi_geojson`` is a GeoJSON geometry in EPSG:4326; it is projected into
    the raster CRS before rasterization so the mask is geodetically correct.
    """
    transformer = Transformer.from_crs(CSSRID, crs, always_xy=True)
    geometry = shapely_shape(aoi_geojson)
    projected = shapely_transform(lambda x, y: transformer.transform(x, y), geometry)
    return geometry_mask(
        [projected],
        out_shape=shape,
        transform=transform,
        invert=True,
    )


def pixel_area_m2(transform: Affine) -> float:
    """Ground area covered by one north-up pixel, in square metres."""
    return float(abs(transform.a * transform.e))


def window_pixel_count(transform: Affine, window: Window) -> int:
    return int(window.width * window.height)
