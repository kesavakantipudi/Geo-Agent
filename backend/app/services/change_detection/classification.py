"""Deterministic change classification over aligned index arrays (Phase 6D).

Everything here is pure math over the two aligned per-pixel index arrays, with
explicit validity masks. Change is classified against the **comparison mask**
(valid in both observations): a pixel invalid in either observation is never
assigned a change class — it stays ``invalid`` (code 255) and is excluded from
every percentage, so change percentages always add up to the comparison-valid
pixels only.

Vegetation change (NDVI): ``delta = after - before``; ``delta >= threshold`` is
an *increase*, ``delta <= -threshold`` a *decrease*, otherwise *stable*. Water
change (NDWI): the documented water boundary ``NDWI >= threshold`` (inclusive,
matching the Phase 6B Aqua contract) is applied to each date, then
new/lost/persistent/unchanged transitions are counted.
"""

from __future__ import annotations

from typing import Any

import numpy as np

# Vegetation change-mask class codes (0/1/2) and the invalid sentinel (255).
VEGETATION_STABLE = 0
VEGETATION_INCREASE = 1
VEGETATION_DECREASE = 2
INVALID_CLASS = 255

# Water change-mask class codes.
WATER_UNCHANGED = 0
WATER_NEW = 1
WATER_LOST = 2
WATER_PERSISTENT = 3

# Sentinel-2 L2A NDVI/NDWI values lie in [-1, 1], so a raw delta is in [-2, 2].
DELTA_RANGE_MIN = -2.0
DELTA_RANGE_MAX = 2.0

CHANGE_ENGINE_VERSION = "geoagent-change-detection-v1"


def vegetation_change(
    nd_before: np.ndarray,
    nd_after: np.ndarray,
    before_valid: np.ndarray,
    after_valid: np.ndarray,
    increase_threshold: float,
) -> dict[str, Any]:
    """Classify vegetation change and return delta + class mask (uint8)."""
    if not (0.0 < increase_threshold <= 2.0):
        raise ValueError(
            f"increase_threshold must satisfy 0 < threshold <= 2, got {increase_threshold}."
        )
    valid = before_valid & after_valid
    delta = np.full(nd_before.shape, np.nan, dtype=np.float32)
    delta[valid] = nd_after[valid] - nd_before[valid]
    increase = valid & (delta >= increase_threshold)
    decrease = valid & (delta <= -increase_threshold)
    stable = valid & ~increase & ~decrease
    mask = np.full(nd_before.shape, INVALID_CLASS, dtype=np.uint8)
    mask[stable] = VEGETATION_STABLE
    mask[increase] = VEGETATION_INCREASE
    mask[decrease] = VEGETATION_DECREASE
    return {
        "delta": delta,
        "valid": valid,
        "increase": increase,
        "decrease": decrease,
        "stable": stable,
        "mask": mask,
        "threshold": increase_threshold,
    }


def water_change(
    ndwi_before: np.ndarray,
    ndwi_after: np.ndarray,
    before_valid: np.ndarray,
    after_valid: np.ndarray,
    water_threshold: float,
) -> dict[str, Any]:
    """Classify water extent change and return transitions + class mask (uint8)."""
    valid = before_valid & after_valid
    before_water = valid & (ndwi_before >= water_threshold)
    after_water = valid & (ndwi_after >= water_threshold)
    unchanged = valid & ~before_water & ~after_water
    new_water = valid & ~before_water & after_water
    lost_water = valid & before_water & ~after_water
    persistent = valid & before_water & after_water
    mask = np.full(ndwi_before.shape, INVALID_CLASS, dtype=np.uint8)
    mask[unchanged] = WATER_UNCHANGED
    mask[new_water] = WATER_NEW
    mask[lost_water] = WATER_LOST
    mask[persistent] = WATER_PERSISTENT
    return {
        "mask": mask,
        "valid": valid,
        "before_water": before_water,
        "after_water": after_water,
        "unchanged": unchanged,
        "new_water": new_water,
        "lost_water": lost_water,
        "persistent": persistent,
        "threshold": water_threshold,
    }


def class_summary(
    count: int,
    comparison_pixels: int,
    area_m2: float | None,
) -> dict[str, Any]:
    pixel_pct = round(float(count / comparison_pixels * 100.0), 4) if comparison_pixels else 0.0
    return {
        "pixel_count": int(count),
        "pixel_pct": pixel_pct,
        "area_m2": round(float(count * area_m2), 2) if area_m2 is not None else None,
    }


def vegetation_summary(
    result: dict[str, Any],
    *,
    area_m2: float,
) -> dict[str, Any]:
    """Aggregate the vegetation classification into a deterministic summary."""
    comparison_pixels = int(result["valid"].sum())
    threshold = float(result["threshold"])
    return {
        "boundary": "increase = delta >= threshold; decrease = delta <= -threshold",
        "threshold": threshold,
        "delta_range": [DELTA_RANGE_MIN, DELTA_RANGE_MAX],
        "comparison_pixels": comparison_pixels,
        "classes": {
            "order": ["increase", "decrease", "stable"],
            "increase": class_summary(int(result["increase"].sum()), comparison_pixels, area_m2),
            "decrease": class_summary(int(result["decrease"].sum()), comparison_pixels, area_m2),
            "stable": class_summary(int(result["stable"].sum()), comparison_pixels, area_m2),
        },
        "invalid_pixel_count": int((~result["valid"]).sum()),
        "limitations_note": vegetation_limitations_note(threshold),
    }


def water_summary(
    result: dict[str, Any],
    *,
    area_m2: float,
) -> dict[str, Any]:
    """Aggregate the water-transition classification into a summary."""
    comparison_pixels = int(result["valid"].sum())
    water_before = int(result["before_water"].sum())
    water_after = int(result["after_water"].sum())
    extent_delta_pixels = water_after - water_before
    water_pixel_pct_before = (
        round(float(water_before / comparison_pixels * 100.0), 4) if comparison_pixels else 0.0
    )
    water_pixel_pct_after = (
        round(float(water_after / comparison_pixels * 100.0), 4) if comparison_pixels else 0.0
    )
    return {
        "threshold": float(result["threshold"]),
        "boundary": "water = NDWI >= threshold (inclusive)",
        "comparison_pixels": comparison_pixels,
        "water_extent": {
            "before_pixels": water_before,
            "after_pixels": water_after,
            "delta_pixels": extent_delta_pixels,
            "before_pct": water_pixel_pct_before,
            "after_pct": water_pixel_pct_after,
        },
        "classes": {
            "order": ["new", "lost", "persistent", "unchanged"],
            "new": class_summary(int(result["new_water"].sum()), comparison_pixels, area_m2),
            "lost": class_summary(int(result["lost_water"].sum()), comparison_pixels, area_m2),
            "persistent": class_summary(
                int(result["persistent"].sum()), comparison_pixels, area_m2
            ),
            "unchanged": class_summary(int(result["unchanged"].sum()), comparison_pixels, area_m2),
        },
        "invalid_pixel_count": int((~result["valid"]).sum()),
        "limitations_note": (
            "Water bodies are detected with the documented NDWI >= threshold "
            "boundary per observation; extent change is over pixels valid in both. "
            "No depth, volume, or discharge claims are implied."
        ),
    }


def vegetation_limitations_note(threshold: float) -> str:
    return (
        f"Increase/decrease is resampled-NDVI delta beyond a documented "
        f"threshold ({threshold:.2f}); it is an observed spectral change, not a "
        "validated crop-health assertion."
    )
