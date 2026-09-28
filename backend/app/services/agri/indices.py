"""Deterministic spectral index definitions and computation (Phase 6A).

Only indices that can be computed deterministically from locally retrieved,
provider-agnostic band assets are registered. The NDVI ratio is invariant to a
constant reflectance scale factor, so the raw Sentinel-2 L2A surface
reflectance values (DN = reflectance x 10000) can be used directly without
explicit scaling; the L2A convention that a value of 0 means "no data" is
honoured through ``zero_is_nodata=True``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.services.agri.classification import SCL_CLOUD_MASK_CLASSES


@dataclass(frozen=True)
class IndexSpec:
    name: str
    label: str
    formula: str
    description: str
    # Semantic role -> asset key, for providers whose band assets use these keys.
    band_roles: dict[str, str]
    units: str = "dimensionless"
    range_min: float = -1.0
    range_max: float = 1.0
    zero_is_nodata: bool = True
    # SCL classes treated as not-clear-sky; exposed in API responses.
    scl_masked_classes: tuple[int, ...] = SCL_CLOUD_MASK_CLASSES


NDVI = IndexSpec(
    name="ndvi",
    label="Normalized Difference Vegetation Index",
    formula="NDVI = (NIR - RED) / (NIR + RED)",
    description=(
        "Vegetation signal derived from Sentinel-2 L2A surface reflectance "
        "(RED = band B04, NIR = band B08). Deterministic ratio; scale-invariant; "
        "no-crop-health, crop-type, or yield claims are implied."
    ),
    band_roles={"red": "B04", "nir": "B08", "cloud_mask": "SCL"},
)

INDEX_REGISTRY: dict[str, IndexSpec] = {"ndvi": NDVI}


def compute_ndvi(
    red: np.ndarray,
    nir: np.ndarray,
    valid: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """NDVI values and a validity mask.

    ``red``/``nir`` are float32 arrays (raw L2A reflectance DN, no-data set to
    NaN by the raster layer). ``valid`` must already exclude no-data / AOI /
    cloud-masked pixels. Pixels where NIR + RED <= 0 (numerically impossible to
    produce a meaningful ratio) are marked invalid. The result is clipped to the
    index range so downstream tiers stay within documented bounds.
    """
    denominator = nir + red
    positive = denominator > 0.0
    ndvi = np.where(positive, (nir - red) / np.where(positive, denominator, 1.0), np.nan)
    ndvi = np.clip(ndvi, NDVI.range_min, NDVI.range_max).astype(np.float32)
    index_valid = valid & positive & np.isfinite(ndvi)
    return ndvi, index_valid
