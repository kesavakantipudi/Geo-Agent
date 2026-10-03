"""Phase 6B unit tests: NDWI math, water classification, statistics, area.

The end-to-end groups exercise ``compute_aqua_index`` against synthetic GeoTIFFs
on the shared windowed analysis core (no live providers, no network).
"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from agri_mocks import clear_scl, cloudy_scl
from aqua_mocks import (
    land_scene,
    mixed_land_water_scene,
    water_scene,
    write_aqua_bands,
)

from app.services.aqua import AquaUnavailable, classification, compute_aqua_index
from app.services.geospatial import statistics
from app.services.geospatial.indices import NDWI, WATER_INDEX_REGISTRY, compute_ndwi

SETTINGS = SimpleNamespace(aqua_min_valid_fraction=0.01, aqua_max_window_pixels=20_000_000)
ACQUIRED = date(2024, 7, 5)


def _run(
    green,
    nir,
    *,
    scl=None,
    mask_clouds=True,
    aoi=None,
    settings=None,
    threshold=0.0,
    b08=None,
):
    from satellite_mocks import POLYGON

    aoi = aoi or POLYGON
    index = WATER_INDEX_REGISTRY["ndwi"]
    directory = Path(tempfile.mkdtemp(prefix="aqua_unit_"))
    if b08 is None:
        b08 = nir
    asset_paths = write_aqua_bands(directory, green, b08, scl=scl)
    role_map = {"B03": "green", "B08": "nir", "SCL": "cloud_mask"}
    paths = {role_map[key]: path for key, path in asset_paths.items()}
    retrievals = {"green": 1, "nir": 2}
    if scl is not None:
        retrievals["cloud_mask"] = 3
    return compute_aqua_index(
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
        threshold=threshold,
        settings=settings or SETTINGS,
    )


# ---------------------------------------------------------------------------
# NDWI math (shared normalized-difference core)
# ---------------------------------------------------------------------------


def test_ndwi_known_values():
    green = np.array([[0.3, 0.15], [0.25, 0.4]], dtype=np.float32)
    nir = np.array([[0.1, 0.25], [0.35, 0.1]], dtype=np.float32)
    values, mask = compute_ndwi(green, nir, np.ones((2, 2), dtype=bool))
    assert np.allclose(
        values,
        np.array([[0.5, -0.25], [-0.1667, 0.6]], dtype=np.float32),
        atol=1e-3,
    )
    assert mask.all()


def test_ndwi_negative_values_allowed():
    green = np.array([0.2], dtype=np.float32)
    nir = np.array([0.6], dtype=np.float32)
    values, mask = compute_ndwi(green, nir, np.ones(1, dtype=bool))
    assert abs(values[0] - (-0.5)) < 1e-3
    assert mask[0]


def test_ndwi_division_by_zero_marked_invalid():
    values, mask = compute_ndwi(
        np.array([0.0], dtype=np.float32), np.array([0.0], dtype=np.float32), np.ones(1, dtype=bool)
    )
    assert not mask[0]
    assert np.isnan(values[0])


def test_ndwi_nan_input_marked_invalid():
    values, mask = compute_ndwi(
        np.array([np.nan], dtype=np.float32),
        np.array([0.5], dtype=np.float32),
        np.ones(1, dtype=bool),
    )
    assert not mask[0]
    assert np.isnan(values[0])


# ---------------------------------------------------------------------------
# Water classification (documented threshold, inclusive boundary)
# ---------------------------------------------------------------------------


def test_classify_threshold_boundary_is_inclusive():
    values = np.array([0.0, 0.0, -0.1, 0.5])
    valid = np.ones(4, dtype=bool)
    parts = classification.classify(values, valid, threshold=0.0)
    assert parts["water"] == 3  # 0.0 >= 0.0 counts as water (inclusive)
    assert parts["non_water"] == 1
    assert parts["invalid"] == 0


def test_classify_invalid_pixels_never_water():
    values = np.array([9.0, -9.0])
    valid = np.array([False, False])
    parts = classification.classify(values, valid, threshold=0.0)
    assert parts["water"] == 0
    assert parts["non_water"] == 0
    assert parts["invalid"] == 2


def test_water_summary_areas():
    values = np.full((4, 4), 0.5, dtype=np.float32)
    valid = np.ones((4, 4), dtype=bool)
    summary = classification.water_summary(
        values,
        valid,
        threshold=0.0,
        valid_pixel_count=16,
        aoi_pixel_count=16,
        pixel_area_m2=100.0,
    )
    assert summary["water"]["pixel_count"] == 16
    assert summary["water"]["pixel_pct"] == 100.0
    assert summary["water"]["area_m2"] == 1600.0
    assert summary["water"]["pct_of_aoi_area"] == 100.0
    assert summary["non_water"]["pixel_count"] == 0
    assert summary["invalid_pixel_count"] == 0
    assert summary["aoi_area_m2"] == 1600.0
    assert summary["threshold"] == 0.0
    assert "not a validated" in summary["threshold_source"]


def test_water_summary_threshold_override_changes_split():
    values = np.array([0.5, 0.5, -0.2, -0.2], dtype=np.float32)
    valid = np.ones(4, dtype=bool)
    at_zero = classification.water_summary(
        values, valid, threshold=0.0, valid_pixel_count=4, aoi_pixel_count=4, pixel_area_m2=1.0
    )
    assert at_zero["water"]["pixel_count"] == 2
    at_point_three = classification.water_summary(
        values, valid, threshold=0.3, valid_pixel_count=4, aoi_pixel_count=4, pixel_area_m2=1.0
    )
    assert at_point_three["water"]["pixel_count"] == 2
    above = classification.water_summary(
        values, valid, threshold=0.6, valid_pixel_count=4, aoi_pixel_count=4, pixel_area_m2=1.0
    )
    assert above["water"]["pixel_count"] == 0
    assert above["non_water"]["pixel_count"] == 4


# ---------------------------------------------------------------------------
# Statistics (shared)
# ---------------------------------------------------------------------------


def test_describe_and_valid_fraction_shared():
    values = np.array([np.nan, 1.0, 3.0], dtype=np.float32)
    stats = statistics.describe(values, np.ones(3, dtype=bool))
    assert stats["mean"] == pytest.approx(2.0)
    assert statistics.valid_fraction(30, 40) == 75.0


# ---------------------------------------------------------------------------
# End-to-end compute_aqua_index against synthetic GeoTIFFs
# ---------------------------------------------------------------------------


def test_full_water_analysis():
    green, nir = water_scene()
    payload = _run(green, nir, scl=clear_scl())
    assert payload["status"] == "completed"
    assert payload["index"]["name"] == "ndwi"
    assert payload["index"]["range"] == [-1.0, 1.0]
    stats = payload["statistics"]
    assert stats["valid_pixel_pct"] == 100.0
    assert stats["mean"] == pytest.approx(1700 / 3100, abs=1e-4)
    water = payload["classification"]["water"]
    assert water["pixel_count"] == stats["aoi_pixel_count"]
    assert water["pixel_pct"] == 100.0
    assert water["pct_of_aoi_area"] == 100.0
    assert water["area_m2"] > 0
    assert payload["classification"]["non_water"]["pixel_count"] == 0
    assert payload["classification"]["invalid_pixel_count"] == 0
    assert payload["classification"]["threshold"] == 0.0
    assert payload["cloud"]["cloud_mask_available"] is True
    assert {band["role"] for band in payload["bands"]} == {"green", "nir", "cloud_mask"}
    assert payload["processing"]["pixel_area_m2"] > 0
    assert payload["warnings"] == []


def test_land_scene_has_no_water():
    green, nir = land_scene()
    payload = _run(green, nir, mask_clouds=False)
    assert payload["statistics"]["mean"] == pytest.approx(-0.2, abs=1e-4)
    assert payload["classification"]["water"]["pixel_count"] == 0
    assert (
        payload["classification"]["non_water"]["pixel_count"]
        == payload["statistics"]["valid_pixel_count"]
    )


def test_mixed_scene_split_with_threshold_override():
    green, nir = mixed_land_water_scene()
    at_zero = _run(green, nir, mask_clouds=False, threshold=0.0)
    assert at_zero["classification"]["water"]["pixel_pct"] == 50.0
    assert at_zero["classification"]["non_water"]["pixel_pct"] == 50.0

    high = _run(green, nir, mask_clouds=False, threshold=0.6)
    assert high["classification"]["water"]["pixel_count"] == 0
    assert high["classification"]["threshold"] == 0.6

    low = _run(green, nir, mask_clouds=False, threshold=-0.3)
    assert low["classification"]["water"]["pixel_pct"] == 100.0


def test_cloud_masking_excludes_cloud_pixels():
    green, nir = water_scene()
    payload = _run(green, nir, scl=cloudy_scl())  # top half = cloud
    assert payload["cloud"]["cloud_mask_available"] is True
    assert payload["statistics"]["valid_pixel_pct"] == 50.0
    assert payload["classification"]["water"]["pixel_pct"] == 100.0  # all remaining are water
    assert (
        payload["classification"]["water"]["pixel_count"]
        == payload["statistics"]["valid_pixel_count"]
    )
    assert (
        payload["classification"]["invalid_pixel_count"]
        == payload["statistics"]["aoi_pixel_count"] // 2
    )


def test_missing_scl_yields_warning_and_unmasked_analysis():
    green, nir = water_scene()
    payload = _run(green, nir, scl=None, mask_clouds=True)
    assert payload["cloud"]["cloud_mask_available"] is False
    assert any("unmasked" in item for item in payload["warnings"])
    assert payload["statistics"]["valid_pixel_pct"] == 100.0


def test_mask_clouds_disabled_ignores_clouds():
    green, nir = water_scene()
    payload = _run(green, nir, scl=cloudy_scl(), mask_clouds=False)
    assert payload["cloud"]["mask_clouds"] is False
    assert payload["statistics"]["valid_pixel_pct"] == 100.0


def test_zero_bands_treated_as_nodata():
    green, nir = water_scene()
    green[0:10, :] = 0
    nir[0:10, :] = 0
    payload = _run(green, nir, mask_clouds=False)
    assert payload["statistics"]["valid_pixel_pct"] == 75.0
    assert payload["statistics"]["mean"] == pytest.approx(1700 / 3100, abs=1e-4)


def test_scale_invariance_of_ndwi():
    low = _run(
        np.full((16, 16), 120, dtype=np.uint16),
        np.full((16, 16), 350, dtype=np.uint16),
        mask_clouds=False,
    )
    high = _run(
        np.full((16, 16), 2400, dtype=np.uint16),
        np.full((16, 16), 7000, dtype=np.uint16),
        mask_clouds=False,
    )
    assert low["statistics"]["mean"] == pytest.approx(high["statistics"]["mean"], abs=1e-4)


# ---------------------------------------------------------------------------
# Unavailable states (explicit, never fabricated)
# ---------------------------------------------------------------------------


def test_insufficient_valid_pixels_unavailable():
    green = np.zeros((16, 16), dtype=np.uint16)
    nir = np.zeros((16, 16), dtype=np.uint16)
    with pytest.raises(AquaUnavailable) as exc_info:
        _run(green, nir, mask_clouds=False)
    assert exc_info.value.code == "insufficient_valid_pixels"


def test_bands_not_retrieved_unavailable():
    green, nir = water_scene()
    directory = Path(tempfile.mkdtemp(prefix="aqua_unit_"))
    asset_paths = write_aqua_bands(directory, green, nir)
    paths = {"nir": asset_paths["B08"]}  # green missing
    with pytest.raises(AquaUnavailable) as exc_info:
        compute_aqua_index(
            aoi_geojson={
                "type": "Polygon",
                "coordinates": [
                    [[77.5, 12.9], [77.6, 12.9], [77.6, 13.0], [77.5, 13.0], [77.5, 12.9]]
                ],
            },
            index=NDWI,
            band_paths=paths,
            band_retrievals={"nir": 2},
            acquisition_date=ACQUIRED,
            cloud_cover=5.0,
            provider="planetary-computer",
            platform="sentinel-2a",
            provider_scene_id="S2A_test",
            mask_clouds=False,
            threshold=0.0,
            settings=SETTINGS,
        )
    assert exc_info.value.code == "bands_not_retrieved"


def test_band_grid_mismatch_unavailable():
    green, nir = water_scene()
    b08_bigger = np.full((44, 44), 700, dtype=np.uint16)
    with pytest.raises(AquaUnavailable) as exc_info:
        _run(green, nir, b08=b08_bigger, mask_clouds=False)
    assert exc_info.value.code == "band_grid_mismatch"


def test_no_overlap_unavailable():
    far_away = {
        "type": "Polygon",
        "coordinates": [
            [[106.0, -6.0], [106.1, -6.0], [106.1, -6.1], [106.0, -6.1], [106.0, -6.0]]
        ],
    }
    green, nir = water_scene()
    with pytest.raises(AquaUnavailable) as exc_info:
        _run(green, nir, mask_clouds=False, aoi=far_away)
    assert exc_info.value.code == "no_overlap"


def test_window_too_large_unavailable():
    green, nir = water_scene()
    tiny = SimpleNamespace(aqua_min_valid_fraction=0.01, aqua_max_window_pixels=4)
    with pytest.raises(AquaUnavailable) as exc_info:
        _run(green, nir, mask_clouds=False, settings=tiny)
    assert exc_info.value.code == "aoi_window_too_large"


def test_provenance_payload():
    green, nir = water_scene()
    payload = _run(green, nir, scl=clear_scl())
    assert payload["processing"]["algorithm"].endswith("-v1")
    assert payload["processing"]["acquisition_date"] == "2024-07-05"
    assert payload["processing"]["provider"] == "planetary-computer"
    assert payload["processing"]["zero_as_nodata"] is True
    assert payload["processing"]["scl_masked_classes"] == [0, 1, 3, 8, 9, 10, 11]
    assert payload["statistics"]["units"] == "dimensionless"
    assert payload["statistics"]["range"] == [-1.0, 1.0]
    assert all(band["retrieval_id"] > 0 for band in payload["bands"])
