"""Synthetic NDWI-ready GeoTIFF fixtures for Phase 6B water-analysis tests.

The satellite download mock serves opaque bytes, never real rasters, so the
aqua tests generate their own small GeoTIFF GREEN/NIR (B03/B08) band files
(clearly synthetic test data) and seed ``satellite_retrievals`` rows pointing
at them, exactly like a completed download would. Bands are written on the same
UTM 32643 grid used by the agri fixtures so the AOI masking is exercised.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from agri_mocks import write_band

# Surface reflectance x 10000 (Sentinel-2 L2A convention).
WATER_GREEN = 2400  # NDWI = (2400 - 700) / 3100 ~ 0.5484
WATER_NIR = 700
LAND_GREEN = 3000  # NDWI = (3000 - 4500) / 7500 = -0.2
LAND_NIR = 4500


def write_aqua_bands(
    directory: Path, green: np.ndarray, nir: np.ndarray, scl=None
) -> dict[str, str]:
    """Write B03/B08(/SCL) TIFFs and return {asset_key: absolute path}."""
    directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "B03": write_band(directory / "B03.tif", green),
        "B08": write_band(directory / "B08.tif", nir),
    }
    if scl is not None:
        paths["SCL"] = write_band(directory / "SCL.tif", scl)
    return paths


def water_scene(size: int = 40) -> tuple[np.ndarray, np.ndarray]:
    green = np.full((size, size), WATER_GREEN, dtype=np.uint16)
    nir = np.full((size, size), WATER_NIR, dtype=np.uint16)
    return green, nir


def land_scene(size: int = 40) -> tuple[np.ndarray, np.ndarray]:
    green = np.full((size, size), LAND_GREEN, dtype=np.uint16)
    nir = np.full((size, size), LAND_NIR, dtype=np.uint16)
    return green, nir


def mixed_land_water_scene(size: int = 40) -> tuple[np.ndarray, np.ndarray]:
    half = size // 2
    green = np.full((size, size), LAND_GREEN, dtype=np.uint16)
    nir = np.full((size, size), LAND_NIR, dtype=np.uint16)
    green[:half, :] = WATER_GREEN
    nir[:half, :] = WATER_NIR
    return green, nir
