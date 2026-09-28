"""Deterministic vegetation-condition tiers for NDVI (Phase 6A).

The tiers below are heuristic reference groupings built from typical
Sentinel-2 L2A surface-reflectance NDVI ranges observed for broad land-cover
classes. They are intentionally kept as transparent constants so callers can
see the exact boundaries that produced a result. They are **not** a validated
crop-health, crop-type, or yield model: any claim inferred from a tier must
stay at the level of "relative vegetation signal / vegetation condition", and
the heuristic nature is surfaced in API responses.
"""

from __future__ import annotations

import numpy as np

# Sentinel-2 Scene Classification Layer classes treated as "not clear sky".
# 0=NO_DATA, 1=SATURATED/DEFECTIVE, 3=CLOUD_SHADOWS, 8/9=CLOUD (med/high),
# 10=THIN_CIRRUS, 11=SNOW/ICE. 4=vegetation / 5=not-vegetated / 6=water /
# 7=unclassified are kept as valid pixels when masking clouds.
SCL_CLOUD_MASK_CLASSES = (0, 1, 3, 8, 9, 10, 11)

HEURISTIC_NOTE = (
    "Heuristic reference vegetation-condition tiers (documented thresholds), "
    "not a validated crop-health or yield model."
)

# Ascending bands: ``min <= value < max`` for every tier except the last
# (``value >= min``). ``min``/``max`` are None at the open ends.
NDVI_TIER_DEFINITIONS = (
    {
        "tier": "very_low",
        "label": "Very low",
        "min": None,
        "max": 0.10,
        "description": (
            "No meaningful healthy-vegetation signal (e.g. bare soil, built-up, "
            "water or harvested fields)."
        ),
    },
    {
        "tier": "low",
        "label": "Low",
        "min": 0.10,
        "max": 0.25,
        "description": "Weak or sparse vegetation signal (fallow, sparse or emerging cover).",
    },
    {
        "tier": "moderate",
        "label": "Moderate",
        "min": 0.25,
        "max": 0.40,
        "description": "Moderate vegetation signal; mixed or partially stressed cover.",
    },
    {
        "tier": "high",
        "label": "High",
        "min": 0.40,
        "max": 0.60,
        "description": "Strong vegetation signal; dense, photosynthetically active cover.",
    },
    {
        "tier": "very_high",
        "label": "Very high",
        "min": 0.60,
        "max": None,
        "description": "Very strong vegetation signal; very dense cover.",
    },
)

# Deterministic tie-break when several tiers share the maximum pixel share:
# the tier with the lowest NDVI wins (an ascending sort on ``high``). This
# keeps repeated runs on the same input byte-identical.


def _high_float(item: dict) -> float:
    return item["high"] if item["high"] is not None else float("inf")


def tier_for_value(value: float) -> dict:
    """Return the tier definition a single NDVI value falls into."""
    for tier in NDVI_TIER_DEFINITIONS:
        lo = tier["min"]
        hi = tier["max"]
        if lo is None and hi is not None and value < hi:
            return tier
        if lo is not None and hi is not None and lo <= value < hi:
            return tier
        if lo is not None and hi is None and value >= lo:
            return tier
    return NDVI_TIER_DEFINITIONS[-1]


def tier_histogram(values: np.ndarray, valid: np.ndarray) -> list[dict]:
    """Share of valid pixels in each tier, as ``pixel_pct`` (0-100)."""
    data = values[valid]
    total = int(valid.sum())
    histogram: list[dict] = []
    for definition in NDVI_TIER_DEFINITIONS:
        lo = definition["min"]
        hi = definition["max"]
        if lo is None:
            selected = data[data < hi]
        elif hi is None:
            selected = data[data >= lo]
        else:
            selected = data[(data >= lo) & (data < hi)]
        histogram.append(
            {
                "tier": definition["tier"],
                "label": definition["label"],
                "low": definition["min"],
                "high": definition["max"],
                "description": definition["description"],
                "pixel_pct": round(float(selected.size / total * 100.0), 4) if total else 0.0,
            }
        )
    return histogram


def dominant_tier(histogram: list[dict]) -> dict:
    """Tier with the largest pixel share (deterministic tie-break documented)."""
    ordered = sorted(histogram, key=lambda item: (-item["pixel_pct"], _high_float(item)))
    return ordered[0]
