"""Deterministic open-water / non-water classification for NDWI (Phase 6B).

WDWI (as computed in :mod:`app.services.geospatial.indices`) is partitioned by a
single documented threshold: ``ndwi >= threshold`` is water, everything below is
non-water. The threshold is a transparent heuristic (default 0.0, configurable
per analysis and echoed in the response) so callers can see the exact boundary
that produced a result. It is **not** a validated water-quality, depth, or
discharge model: vegetation, built-up, cloud shadows, turbidity, snow/ice, and
mixed pixels all raise the false-positive / false-negative risk, and that
limitation is surfaced in API responses.
"""

from __future__ import annotations

import numpy as np

LIMITATIONS_NOTE = (
    "Documented heuristic water threshold (NDWI >= threshold is open water), "
    "not a validated water-quality, depth, or discharge model. Vegetation, "
    "built-up, cloud shadows, turbidity, snow/ice, and mixed pixels can produce "
    "false positives or negatives."
)

DEFAULT_THRESHOLD = 0.0
BOUNDARY = "water = NDWI >= threshold (inclusive)"


def classify(values: np.ndarray, valid: np.ndarray, threshold: float) -> dict:
    """Partition ``values`` into water / non-water / invalid per ``threshold``.

    ``values`` is the float32 index array; ``valid`` is the masked-valid mask.
    Water is ``ndwi >= threshold`` (inclusive) restricted to ``valid`` pixels.
    Invalid pixels are never coerced to either class. Returns integer counts.
    """
    water = (values >= threshold) & valid
    non_water = (values < threshold) & valid
    invalid = ~valid
    return {
        "water": int(water.sum()),
        "non_water": int(non_water.sum()),
        "invalid": int(invalid.sum()),
    }


def water_summary(
    values: np.ndarray,
    valid: np.ndarray,
    *,
    threshold: float,
    valid_pixel_count: int,
    aoi_pixel_count: int,
    pixel_area_m2: float,
) -> dict:
    """Assemble the auditable classification block for an NDWI result."""
    parts = classify(values, valid, threshold)
    water_count = parts["water"]
    non_water_count = parts["non_water"]
    invalid_count = parts["invalid"]
    water_area = float(water_count) * pixel_area_m2
    aoi_area = float(aoi_pixel_count) * pixel_area_m2
    return {
        "label": "Open water / non-water",
        "threshold": round(float(threshold), 6),
        "boundary": BOUNDARY,
        "threshold_source": LIMITATIONS_NOTE,
        "water": {
            "pixel_count": water_count,
            "pixel_pct": round(float(water_count / valid_pixel_count) * 100.0, 4)
            if valid_pixel_count
            else 0.0,
            "area_m2": round(water_area, 2),
            "pct_of_aoi_area": round(water_area / aoi_area * 100.0, 4) if aoi_area > 0 else 0.0,
        },
        "non_water": {
            "pixel_count": non_water_count,
            "pixel_pct": round(float(non_water_count / valid_pixel_count) * 100.0, 4)
            if valid_pixel_count
            else 0.0,
            "area_m2": round(float(non_water_count) * pixel_area_m2, 2),
        },
        "invalid_pixel_count": invalid_count,
        "aoi_area_m2": round(aoi_area, 2),
    }
