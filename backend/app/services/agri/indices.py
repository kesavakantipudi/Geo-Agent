"""Legacy import shim for spectral index definitions (moved to geospatial.indices).

``indices`` lives in the shared ``geospatial`` package so every derived
intelligence service (agriculture now, water next) uses one implementation.
Both NDVI and NDWI share the normalized-difference ratio core.
"""

from app.services.geospatial.indices import (
    INDEX_REGISTRY,
    NDVI,
    NDWI,
    SCL_CLOUD_MASK_CLASSES,
    WATER_INDEX_REGISTRY,
    IndexSpec,
    compute_ndvi,
    compute_ndwi,
    normalized_difference,
)

__all__ = [
    "INDEX_REGISTRY",
    "WATER_INDEX_REGISTRY",
    "NDVI",
    "NDWI",
    "IndexSpec",
    "SCL_CLOUD_MASK_CLASSES",
    "compute_ndvi",
    "compute_ndwi",
    "normalized_difference",
]
