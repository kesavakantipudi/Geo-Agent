"""Synthetic Sentinel-2-like GeoTIFF fixtures and retrieval seeding for Phase 6A.

The satellite download mock serves opaque bytes, never real rasters, so the
agri tests generate their own small GeoTIFF band files (clearly synthetic test
data) and seed ``satellite_retrievals`` rows pointing at them, exactly like a
completed download would.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.transform import from_origin

# UTM zone that covers Bengaluru (77.5E, 12.9N), matching the mock AOI.
UTM_CRS = CRS.from_epsg(32643)

AOI_CORNERS = [(lon, lat) for lon in (77.5, 77.6) for lat in (12.9, 13.0)]


def write_band(path: Path, values: np.ndarray, *, crs=UTM_CRS) -> str:
    """Write one array as a GeoTIFF whose footprint exactly covers the AOI."""
    height, width = values.shape[-2:]
    transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    eastings = []
    northings = []
    for lon, lat in AOI_CORNERS:
        e, n = transformer.transform(lon, lat)
        eastings.append(e)
        northings.append(n)
    res_e = (max(eastings) - min(eastings)) / width
    res_n = (max(northings) - min(northings)) / height
    transform = from_origin(min(eastings), max(northings), res_e, res_n)
    dtype = "uint16" if values.dtype == np.uint16 else "uint8"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=1,
        dtype=dtype,
        crs=crs,
        transform=transform,
    ) as src:
        src.write(values, 1)
    return str(path)


def write_scene_bands(
    directory: Path, red: np.ndarray, nir: np.ndarray, scl=None
) -> dict[str, str]:
    """Write B04/B08(/SCL) TIFFs and return {asset_key: absolute path}."""
    directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "B04": write_band(directory / "B04.tif", red),
        "B08": write_band(directory / "B08.tif", nir),
    }
    if scl is not None:
        paths["SCL"] = write_band(directory / "SCL.tif", scl)
    return paths


def seed_retrieval(
    scene_id: int, asset_key: str, content_path: str | Path, *, actor_id=None
) -> None:
    """Copy a band file into the retrieval store and record a completed retrieval."""
    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.models import SatelliteRetrieval

    storage = Path(get_settings().retrieval_storage_dir)
    relative = f"{scene_id}/{asset_key}.tif"
    target = storage / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(Path(content_path).read_bytes())

    with SessionLocal() as db:
        db.add(
            SatelliteRetrieval(
                scene_id=scene_id,
                analysis_session_id=None,
                requested_by=actor_id,
                asset_key=asset_key,
                status="completed",
                stored_path=relative,
                size_bytes=target.stat().st_size,
                error=None,
                completed_at=datetime.now(UTC),
            )
        )
        db.commit()


# Convenience synthetic scenes (values are reflectance x 10000 like S2 L2A).
REF_VEGETATION = 800  # NDVI ~ 0.698 with NIR=4500
REF_NIR_VEGETATION = 4500
REF_WATER = 400  # NDVI ~ -0.333 with RED=800
REF_RED_WATER = 800


def dense_vegetation_scene(size: int = 40) -> tuple[np.ndarray, np.ndarray]:
    red = np.full((size, size), REF_VEGETATION, dtype=np.uint16)
    nir = np.full((size, size), REF_NIR_VEGETATION, dtype=np.uint16)
    return red, nir


def mixed_field_water_scene(size: int = 40) -> tuple[np.ndarray, np.ndarray]:
    half = size // 2
    red = np.full((size, size), REF_RED_WATER, dtype=np.uint16)
    nir = np.full((size, size), REF_WATER, dtype=np.uint16)
    red[half:, :] = REF_VEGETATION
    nir[half:, :] = REF_NIR_VEGETATION
    return red, nir


def clear_scl(size: int = 40) -> np.ndarray:
    return np.full((size, size), 4, dtype=np.uint8)  # 4 = vegetation (valid)


def cloudy_scl(size: int = 40) -> np.ndarray:
    scl = clear_scl(size)
    scl[: size // 2, :] = 9  # cloud high probability over the top half
    return scl


def empty_bands(size: int = 40) -> tuple[np.ndarray, np.ndarray]:
    return np.zeros((size, size), dtype=np.uint16), np.zeros((size, size), dtype=np.uint16)
