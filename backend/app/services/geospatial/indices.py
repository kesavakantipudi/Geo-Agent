"""Deterministic spectral index definitions and computation (shared Phase 6 core).

Only indices that can be computed deterministically from locally retrieved,
provider-agnostic band assets are registered. Both NDVI and NDWI are
normalized-difference ratios invariant to a constant reflectance scale factor,
so the raw Sentinel-2 L2A surface reflectance values (DN = reflectance x 10000)
can be used directly without explicit scaling; the L2A convention that a value
of 0 means "no data" is honoured through ``zero_is_nodata=True``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.services.geospatial.analysis import normalized_difference

# Sentinel-2 Scene Classification Layer classes treated as "not clear sky".
# 0=NO_DATA, 1=SATURATED/DEFECTIVE, 3=CLOUD_SHADOWS, 8/9=CLOUD (med/high),
# 10=THIN_CIRRUS, 11=SNOW/ICE. 4=vegetation / 5=not-vegetated / 6=water /
# 7=unclassified are kept as valid pixels when masking clouds.
SCL_CLOUD_MASK_CLASSES = (0, 1, 3, 8, 9, 10, 11)


@dataclass(frozen=True)
class IndexSpec:
    name: str
    label: str
    formula: str
    description: str
    # Semantic role -> asset key, for providers whose band assets use these keys.
    band_roles: dict[str, str]
    # ``(numerator - denominator) / (numerator + denominator)`` roles.
    numerator_role: str = "nir"
    denominator_role: str = "red"
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

NDWI = IndexSpec(
    name="ndwi",
    label="Normalized Difference Water Index",
    formula="NDWI = (GREEN - NIR) / (GREEN + NIR)",
    description=(
        "Open-water signal derived from Sentinel-2 L2A surface reflectance "
        "(GREEN = band B03, NIR = band B08). Deterministic ratio; scale-invariant; "
        "no water-quality, depth, or discharge claims are implied."
    ),
    band_roles={"green": "B03", "nir": "B08", "cloud_mask": "SCL"},
    numerator_role="green",
    denominator_role="nir",
)

INDEX_REGISTRY: dict[str, IndexSpec] = {"ndvi": NDVI}
WATER_INDEX_REGISTRY: dict[str, IndexSpec] = {"ndwi": NDWI}


def compute_ndvi(
    red: np.ndarray,
    nir: np.ndarray,
    valid: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """NDVI values and a validity mask (delegates to the shared ratio core)."""
    return normalized_difference(nir, red, valid, NDVI.range_min, NDVI.range_max)


def compute_ndwi(
    green: np.ndarray,
    nir: np.ndarray,
    valid: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """NDWI values and a validity mask (delegates to the shared ratio core)."""
    return normalized_difference(green, nir, valid, NDWI.range_min, NDWI.range_max)
