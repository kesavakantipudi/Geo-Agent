"""Phase 6A unit tests (no database): NDVI math, tiers, and raster analysis.

The end-to-end groups exercise ``compute_agri_index`` against synthetic GeoTIFF
band files generated on the fly, so windowed reads, AOI masking, cloud
masking, reprojection, and the unavailable states are all covered without a
database.
"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from agri_mocks import (
    clear_scl,
    cloudy_scl,
    dense_vegetation_scene,
    mixed_field_water_scene,
    write_scene_bands,
)

from app.services.agri import (
    AgriUnavailable,
    bands,
    classification,
    compute_agri_index,
    indices,
    statistics,
)

SETTINGS = SimpleNamespace(agri_min_valid_fraction=0.01, agri_max_window_pixels=20_000_000)
ACQUIRED = date(2024, 7, 5)


def _run(red, nir, *, scl=None, mask_clouds=True, aoi=None, settings=None, index=None, b08=None):
    from satellite_mocks import POLYGON

    aoi = aoi or POLYGON
    index = index or indices.NDVI
    directory = Path(tempfile.mkdtemp(prefix="agri_unit_"))
    if b08 is None:
        b08 = nir
    asset_paths = write_scene_bands(directory, red, b08, scl=scl)
    role_map = {"B04": "red", "B08": "nir", "SCL": "cloud_mask"}
    paths = {role_map[key]: path for key, path in asset_paths.items()}
    retrievals = {"red": 1, "nir": 2}
    if scl is not None:
        retrievals["cloud_mask"] = 3
    return compute_agri_index(
        aoi_geojson=aoi,
        index=index,
        band_paths=paths,
        band_retrievals=retrievals,
        acquisition_date=ACQUIRED,
        cloud_cover=5.0,
        provider="planetary-computer",
        platform="sentinel-2a",
        provider_scene_id="S2A_test",
        mask_clouds=mask_clouds,
        settings=settings or SETTINGS,
    )


# ---------------------------------------------------------------------------
# Index math
# ---------------------------------------------------------------------------


def test_ndvi_known_values():
    red = np.array([[0.1, 0.05], [0.2, 0.3]], dtype=np.float32)
    nir = np.array([[0.5, 0.3], [0.8, 0.6]], dtype=np.float32)
    valid = np.ones((2, 2), dtype=bool)
    values, mask = indices.compute_ndvi(red, nir, valid)
    expected = np.array([[0.6667, 0.7143], [0.6, 0.3333]], dtype=np.float32)
    assert np.allclose(values, expected, atol=1e-3)
    assert mask.all()


def test_ndvi_negative_values_allowed():
    red = np.array([0.8], dtype=np.float32)
    nir = np.array([0.4], dtype=np.float32)
    values, mask = indices.compute_ndvi(red, nir, np.ones(1, dtype=bool))
    assert abs(values[0] - (-0.3333)) < 1e-3
    assert mask[0]


def test_ndvi_division_by_zero_marked_invalid():
    red = np.array([0.0], dtype=np.float32)
    nir = np.array([0.0], dtype=np.float32)
    values, mask = indices.compute_ndvi(red, nir, np.ones(1, dtype=bool))
    assert not mask[0]
    assert np.isnan(values[0])


def test_ndvi_nan_input_marked_invalid():
    red = np.array([np.nan], dtype=np.float32)
    nir = np.array([0.5], dtype=np.float32)
    values, mask = indices.compute_ndvi(red, nir, np.ones(1, dtype=bool))
    assert not mask[0]
    assert np.isnan(values[0])


def test_ndvi_invalid_input_cannot_be_rescued_by_valid_flag():
    red = np.array([np.nan, 0.1], dtype=np.float32)
    nir = np.array([0.5, 0.5], dtype=np.float32)
    valid = np.array([True, True])
    values, mask = indices.compute_ndvi(red, nir, valid)
    assert not mask[0]
    assert mask[1]


# ---------------------------------------------------------------------------
# Classification tiers
# ---------------------------------------------------------------------------


def test_tier_boundaries():
    cases = [
        (-0.99, "very_low"),
        (0.0999, "very_low"),
        (0.10, "low"),
        (0.2499, "low"),
        (0.25, "moderate"),
        (0.3999, "moderate"),
        (0.40, "high"),
        (0.5999, "high"),
        (0.60, "very_high"),
        (0.99, "very_high"),
    ]
    for value, expected in cases:
        assert classification.tier_for_value(value)["tier"] == expected, value


def test_histogram_shares():
    values = np.array([0.9, 0.9, 0.9, 0.15, 0.15, 0.05], dtype=np.float32)
    histogram = classification.tier_histogram(values, np.ones(6, dtype=bool))
    by_tier = {item["tier"]: item["pixel_pct"] for item in histogram}
    assert by_tier["very_low"] == pytest.approx(1 / 6 * 100, abs=0.001)
    assert by_tier["low"] == pytest.approx(2 / 6 * 100, abs=0.001)
    assert by_tier["very_high"] == pytest.approx(3 / 6 * 100, abs=0.001)
    assert by_tier["moderate"] == 0.0
    assert by_tier["high"] == 0.0
    assert sum(item["pixel_pct"] for item in histogram) == pytest.approx(100.0)


def test_dominant_tier_and_deterministic_tie_break():
    values = np.array([0.9, 0.9, 0.05, 0.05], dtype=np.float32)  # 50/50 tie
    histogram = classification.tier_histogram(values, np.ones(4, dtype=bool))
    dominant = classification.dominant_tier(histogram)
    assert dominant["tier"] == "very_low"  # documented tie-break: lower NDVI wins
    assert dominant["pixel_pct"] == 50.0


def test_tier_definitions_are_documented_thresholds():
    assert all(
        item["min"] is not None or item["max"] is not None
        for item in classification.NDVI_TIER_DEFINITIONS
    )
    assert "not a validated crop-health or yield model" in classification.HEURISTIC_NOTE


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def test_describe_masked_values_only():
    values = np.array([np.nan, 2.0, 4.0, 6.0, np.nan], dtype=np.float32)
    valid = np.array([True, True, True, True, True])
    stats = statistics.describe(values, valid)
    assert stats == {
        "min": 2.0,
        "max": 6.0,
        "mean": pytest.approx(4.0),
        "median": pytest.approx(4.0),
        "stddev": pytest.approx(1.632993),
    }


def test_describe_empty_returns_none():
    assert statistics.describe(np.array([np.nan]), np.array([True])) is None


def test_valid_fraction():
    assert statistics.valid_fraction(30, 40) == 75.0
    assert statistics.valid_fraction(0, 40) == 0.0
    assert statistics.valid_fraction(10, 0) == 0.0


# ---------------------------------------------------------------------------
# Band resolution
# ---------------------------------------------------------------------------


def test_resolve_ndvi_keys_for_supported_providers():
    assert bands.resolve_band_keys("planetary-computer", "ndvi") == {
        "red": "B04",
        "nir": "B08",
        "cloud_mask": "SCL",
    }
    assert bands.resolve_band_keys("cdse", "ndvi") == {
        "red": "B04",
        "nir": "B08",
        "cloud_mask": "SCL",
    }


def test_unknown_provider_has_no_mapping():
    assert bands.resolve_band_keys("sentinelhub", "ndvi") is None
    assert bands.resolve_band_keys("planetary-computer", "evi") is None


# ---------------------------------------------------------------------------
# End-to-end compute_agri_index against synthetic GeoTIFFs
# ---------------------------------------------------------------------------


def test_dense_vegetation_analysis():
    red, nir = dense_vegetation_scene()
    payload = _run(red, nir, scl=clear_scl())
    assert payload["status"] == "completed"
    assert payload["index"]["name"] == "ndvi"
    assert payload["statistics"]["valid_pixel_pct"] == 100.0
    assert payload["statistics"]["mean"] == pytest.approx(0.698113, abs=1e-4)
    assert payload["classification"]["overall"]["tier"] == "very_high"
    assert payload["classification"]["dominant_tier"]["tier"] == "very_high"
    assert payload["cloud"]["cloud_mask_available"] is True
    assert len(payload["bands"]) == 3
    assert {band["role"] for band in payload["bands"]} == {"red", "nir", "cloud_mask"}
    assert payload["processing"]["pixel_area_m2"] > 0


def test_scale_invariance_of_ndvi():
    low = _run(
        np.full((16, 16), 90, dtype=np.uint16),
        np.full((16, 16), 450, dtype=np.uint16),
        mask_clouds=False,
    )
    high = _run(
        np.full((16, 16), 9000, dtype=np.uint16),
        np.full((16, 16), 45000, dtype=np.uint16),
        mask_clouds=False,
    )
    assert low["statistics"]["mean"] == pytest.approx(high["statistics"]["mean"], abs=1e-4)


def test_cloud_masking_excludes_cloud_pixels():
    red, nir = dense_vegetation_scene()
    payload = _run(red, nir, scl=cloudy_scl())  # top half = cloud
    assert payload["cloud"]["cloud_mask_available"] is True
    assert payload["statistics"]["valid_pixel_pct"] == 50.0
    assert payload["statistics"]["mean"] == pytest.approx(0.698113, abs=1e-4)


def test_missing_scl_yields_warning_and_unmasked_analysis():
    red, nir = dense_vegetation_scene()
    payload = _run(red, nir, scl=None, mask_clouds=True)
    assert payload["cloud"]["cloud_mask_available"] is False
    assert any("unmasked" in item for item in payload["warnings"])
    assert payload["statistics"]["valid_pixel_pct"] == 100.0


def test_zero_bands_treated_as_nodata():
    red, nir = dense_vegetation_scene()
    red[0:10, :] = 0
    nir[0:10, :] = 0
    payload = _run(red, nir, mask_clouds=False)
    assert payload["statistics"]["valid_pixel_pct"] == 75.0
    assert payload["statistics"]["mean"] == pytest.approx(0.698113, abs=1e-4)


def test_insufficient_valid_pixels_unavailable():
    red = np.zeros((16, 16), dtype=np.uint16)
    nir = np.zeros((16, 16), dtype=np.uint16)
    with pytest.raises(AgriUnavailable) as exc_info:
        _run(red, nir, mask_clouds=False)
    assert exc_info.value.code == "insufficient_valid_pixels"


def test_all_clouds_insufficient_valid_pixels():
    red, nir = dense_vegetation_scene()
    with pytest.raises(AgriUnavailable) as exc_info:
        _run(red, nir, scl=np.full((16, 16), 9, dtype=np.uint8))
    assert exc_info.value.code == "insufficient_valid_pixels"


def test_no_overlap_unavailable():

    far_away = {
        "type": "Polygon",
        "coordinates": [
            [[106.0, -6.0], [106.1, -6.0], [106.1, -6.1], [106.0, -6.1], [106.0, -6.0]]
        ],
    }
    red, nir = dense_vegetation_scene()
    with pytest.raises(AgriUnavailable) as exc_info:
        _run(red, nir, mask_clouds=False, aoi=far_away)
    assert exc_info.value.code == "no_overlap"


def test_window_too_large_unavailable():
    red, nir = dense_vegetation_scene()
    tiny = SimpleNamespace(agri_min_valid_fraction=0.01, agri_max_window_pixels=4)
    with pytest.raises(AgriUnavailable) as exc_info:
        _run(red, nir, mask_clouds=False, settings=tiny)
    assert exc_info.value.code == "aoi_window_too_large"


def test_band_grid_mismatch_unavailable():
    red, nir = dense_vegetation_scene()
    b08_bigger = np.full((44, 44), 4500, dtype=np.uint16)
    with pytest.raises(AgriUnavailable) as exc_info:
        _run(red, nir, b08=b08_bigger, mask_clouds=False)
    assert exc_info.value.code == "band_grid_mismatch"


def test_scl_on_different_grid_reprojected():
    red, nir = dense_vegetation_scene()
    scl_coarse = cloudy_scl(size=20)  # half-resolution; must be reprojected
    payload = _run(red, nir, scl=scl_coarse)
    assert payload["cloud"]["cloud_mask_available"] is True
    assert payload["statistics"]["valid_pixel_pct"] == pytest.approx(50.0, abs=0.1)


def test_mixed_field_and_water_dominant_lowest_tier():
    red, nir = mixed_field_water_scene()
    payload = _run(red, nir, mask_clouds=False)
    assert payload["statistics"]["mean"] == pytest.approx(0.182389, abs=1e-4)
    assert payload["classification"]["overall"]["tier"] == "low"
    assert payload["classification"]["dominant_tier"]["tier"] == "very_low"
