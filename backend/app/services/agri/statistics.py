"""Masked statistics over valid index pixels (Phase 6A).

All statistics are computed exclusively over pixels that are simultaneously
inside the AOI, free of no-data, and free of the cloud-mask classes. Pixel
counts and coverage percentages are exact (numpy counts), never estimates.
"""

from __future__ import annotations

import numpy as np


def describe(values: np.ndarray, valid: np.ndarray) -> dict[str, float] | None:
    """Basic statistics of ``values`` restricted to ``valid`` pixels.

    Returns None when no pixel is valid (callers turn that into an explicit
    "insufficient valid pixels" unavailable state).
    """
    data = values[valid]
    if data.size == 0:
        return None
    data = data[np.isfinite(data)]
    if data.size == 0:
        return None
    return {
        "min": round(float(np.min(data)), 6),
        "max": round(float(np.max(data)), 6),
        "mean": round(float(np.mean(data)), 6),
        "median": round(float(np.median(data)), 6),
        "stddev": round(float(np.std(data)), 6),
    }


def valid_fraction(valid_count: int, total_pixels: int) -> float:
    """Valid pixels as a percentage of all AOI pixels (0-100)."""
    if total_pixels <= 0:
        return 0.0
    return round(float(valid_count / total_pixels * 100.0), 4)
